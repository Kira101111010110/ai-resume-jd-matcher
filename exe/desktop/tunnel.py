"""
เปิด ngrok tunnel จากในตัว exe ให้ backend บน Render เรียก /analyze เข้ามาที่เครื่องนี้ได้
  เว็บ (Vercel) → backend (Render) → https://<dev domain ของบัญชี ngrok> → 127.0.0.1:PUBLIC_PORT (public_app)

tunnel ชี้ไปที่พอร์ต public เท่านั้น (มีแค่ POST /analyze ที่ต้องมี X-AI-Token กับ GET /health)
หน้าเว็บ/หน้าตั้งค่าอยู่ที่พอร์ต local ซึ่งไม่ผ่าน tunnel — ดู desktop_app.public_app
เป็นส่วน "ขั้นสูง" ปิดไว้เป็นค่าเริ่มต้น: ไม่มี authtoken หรือปิดสวิตช์ = ไม่เปิดพอร์ต public และไม่ต่อ ngrok เลย

ใช้ ngrok Python SDK (ไม่ต้องแนบ ngrok.exe) รัน asyncio loop ของตัวเองใน thread แยก
ไม่ส่งชื่อโดเมน → ngrok ใช้ dev domain ประจำบัญชี (แผนฟรีได้ 1 ชื่อ ไม่เปลี่ยนทุกครั้งที่เปิด)
ห้าม log authtoken — error จาก SDK มี authtoken ติดมาด้วย ต้องผ่าน scrub_secrets ทุกครั้ง
"""

import asyncio
import logging
import threading

import settings_store
from version import VERSION

PUBLIC_PORT = 8100
FORWARD_TO = f"http://127.0.0.1:{PUBLIC_PORT}"

logger = logging.getLogger("resume-ai-tunnel")

# error ที่ลองใหม่ไปก็ไม่หาย ต้องให้ผู้ใช้แก้ authtoken ก่อน
_FATAL_CODES = {"ERR_NGROK_105", "ERR_NGROK_106", "ERR_NGROK_107", "ERR_NGROK_4018"}
# บัญชีเดียวกันเปิด tunnel อยู่ที่อื่น — ลองใหม่ช้าๆ เผื่ออีกฝั่งปิดไปแล้ว
_IN_USE_CODES = {"ERR_NGROK_108", "ERR_NGROK_334"}
_RETRY_DELAYS = (5, 10, 20, 30, 60)

STATE_LABELS = {
    "inactive": "ไม่ได้เปิด (tunnel ทำงานเฉพาะตอนเปิดผ่านโปรแกรม)",
    "off": "ปิดอยู่",
    "no_authtoken": "ยังไม่ได้ใส่ ngrok authtoken",
    "connecting": "กำลังเชื่อมต่อ…",
    "connected": "เชื่อมต่อแล้ว",
    "reconnecting": "หลุด กำลังต่อใหม่…",
    "error": "เชื่อมต่อไม่สำเร็จ",
}


class PublicServerError(Exception):
    """เปิด server พอร์ต public ไม่ได้ — ข้อความเป็นภาษาไทยพร้อมแสดงผู้ใช้"""


def _describe_ngrok_error(exc: Exception) -> tuple[str, bool, bool]:
    """คืน (ข้อความภาษาไทย, fatal, in_use) — ข้อความผ่าน scrub_secrets แล้ว"""
    args = [str(a) for a in getattr(exc, "args", ())]
    code = next((a for a in args if a.startswith("ERR_NGROK_")), None)
    text = " ".join(args) or str(exc)

    if code in _FATAL_CODES:
        return ("ngrok authtoken ไม่ถูกต้องหรือถูกยกเลิก — คัดลอกใหม่จาก "
                "dashboard.ngrok.com/get-started/your-authtoken แล้วบันทึกอีกครั้ง"), True, False
    if code in _IN_USE_CODES:
        return ("บัญชี ngrok นี้เปิด tunnel อยู่ที่อื่นแล้ว (แผนฟรีเปิดได้ทีละ 1 ที่) — ปิด Resume AI หรือ ngrok "
                "ที่เปิดค้างไว้ในเครื่องอื่น/หน้าต่างอื่นที่ใช้บัญชีเดียวกัน แล้วระบบจะลองต่อใหม่เอง"), False, True
    # ทุก error ของ session ขึ้นต้นด้วย "failed to connect session" เลยดูจากคำอื่นแทน
    lowered = text.lower()
    if code is None and any(w in lowered for w in ("dns", "timed out", "timeout", "connection refused",
                                                    "network", "tcp connect", "unreachable", "io error")):
        return "เชื่อมต่อ ngrok ไม่ได้ (อินเทอร์เน็ตมีปัญหา) — กำลังลองใหม่อัตโนมัติ", False, False
    detail = settings_store.scrub_secrets(text)[:300]
    return f"ngrok แจ้ง error{f' ({code})' if code else ''}: {detail}", False, False


class TunnelManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._status = {"state": "inactive", "message": None, "url": None}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session = None
        self._listener = None
        self._connected_token = None
        self._wake: asyncio.Event | None = None
        self._stopping = False
        self._on_change = None
        self._before_connect = None

    # ---------- สถานะ ----------
    def status(self) -> dict:
        with self._lock:
            st = dict(self._status)
        st["label"] = STATE_LABELS.get(st["state"], st["state"])
        return st

    def _set(self, state: str, message: str | None = None, url: str | None = None):
        with self._lock:
            changed = self._status["state"] != state or self._status["message"] != message
            self._status = {"state": state, "message": message, "url": url}
        if changed:
            logger.info(f"tunnel: {state}" + (f" — {message}" if message else "") + (f" ({url})" if url else ""))
            if self._on_change:
                try:
                    self._on_change(self.status())
                except Exception:
                    pass

    # ---------- เริ่ม/หยุด (เรียกจาก launcher) ----------
    def start(self, on_change=None, before_connect=None):
        """before_connect: เรียกก่อนต่อ ngrok ทุกครั้ง (launcher ใช้เปิด server พอร์ต public ตอนต้องใช้จริงเท่านั้น)
        โยน exception = ต่อไม่ได้ (เช่น พอร์ตถูกโปรแกรมอื่นใช้) ข้อความจะขึ้นในหน้าตั้งค่าส่วนขั้นสูง"""
        self._on_change = on_change
        self._before_connect = before_connect
        ready = threading.Event()

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._wake = asyncio.Event()
            ready.set()
            self._loop.run_until_complete(self._supervise())

        self._thread = threading.Thread(target=run, name="ngrok-tunnel", daemon=True)
        self._thread.start()
        ready.wait(5)

    def apply_settings(self):
        """เรียกหลังเปลี่ยน authtoken / สวิตช์ — ให้ supervisor ตรวจใหม่ทันที"""
        if self._loop and self._wake:
            self._loop.call_soon_threadsafe(self._wake.set)

    def stop(self, timeout: float = 5):
        """ปิด tunnel (ใช้ตอนออกจากโปรแกรม — ต้องปิดก่อนหยุด server)"""
        if not self._loop:
            return
        self._stopping = True
        self.apply_settings()
        if self._thread:
            self._thread.join(timeout)

    # ---------- ภายใน (รันใน loop ของ thread tunnel) ----------
    async def _supervise(self):
        attempt = 0
        while not self._stopping:
            authtoken = settings_store.get_ngrok_authtoken()
            enabled = settings_store.is_tunnel_enabled()
            delay = None

            if not authtoken or not enabled:
                await self._close()
                self._set("off" if authtoken else "no_authtoken")
                attempt = 0
            elif self._listener is not None and authtoken == self._connected_token:
                pass  # ต่ออยู่แล้วด้วย token เดิม — SDK reconnect เองถ้าหลุดชั่วคราว
            else:
                await self._close()
                self._set("connecting")
                try:
                    if self._before_connect:
                        await asyncio.get_running_loop().run_in_executor(None, self._before_connect)
                    await self._connect(authtoken)
                    attempt = 0
                except PublicServerError as e:
                    self._set("error", str(e))
                    delay = 30
                except Exception as e:
                    message, fatal, in_use = _describe_ngrok_error(e)
                    logger.warning(f"tunnel connect failed: {settings_store.scrub_secrets(repr(e))[:300]}")
                    self._set("error", message)
                    if not fatal:   # fatal = รอผู้ใช้แก้ authtoken (apply_settings จะปลุก)
                        delay = 60 if in_use else _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                        attempt += 1

            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=delay or 3600)
            except asyncio.TimeoutError:
                pass
        await self._close()
        self._set("off")

    async def _connect(self, authtoken: str):
        import ngrok

        def on_disconnect(addr, error):
            # SDK พยายามต่อใหม่เองอยู่แล้ว แค่อัปเดตสถานะให้ผู้ใช้เห็น
            if not self._stopping:
                self._set("reconnecting", "การเชื่อมต่อกับ ngrok หลุด กำลังต่อใหม่อัตโนมัติ", self._status.get("url"))

        def on_heartbeat(latency):
            if self._listener is not None and self._status["state"] == "reconnecting":
                self._set("connected", None, self._listener.url())

        self._session = await (
            ngrok.SessionBuilder()
            .authtoken(authtoken)
            .client_info("resume-ai-exe", VERSION)
            .handle_disconnection(on_disconnect)
            .handle_heartbeat(on_heartbeat)
            .connect()
        )
        self._listener = await self._session.http_endpoint().listen_and_forward(FORWARD_TO)
        self._connected_token = authtoken
        self._set("connected", None, self._listener.url())

    async def _close(self):
        listener, session = self._listener, self._session
        self._listener = self._session = self._connected_token = None
        for obj in (listener, session):
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass


manager = TunnelManager()
