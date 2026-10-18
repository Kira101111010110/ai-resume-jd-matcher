"""
ตัวเปิดโปรแกรม (entry point ของ .exe)
  1. ดับเบิลคลิก → ไอคอนขึ้นที่ system tray + แจ้งเตือน "กำลังเปิด Resume AI…" ทันที
  2. เปิด server หน้าเว็บ (127.0.0.1:8000) ก่อนโหลดโมเดล → เปิดเบราว์เซอร์ให้ภายในไม่กี่วินาที
     หน้าเว็บขึ้น "กำลังเตรียมระบบ" และหน้าตั้งค่าครั้งแรกใช้งานได้ระหว่างรอ
  3. โหลดโมเดล SBERT/spaCy (เกือบ 1 นาที) → หน้าเว็บเปลี่ยนเป็นพร้อมวิเคราะห์เอง + tray แจ้ง "พร้อมใช้งาน"
  4. (ขั้นสูง) ถ้าใส่ ngrok authtoken + เปิดสวิตช์ไว้ เปิด server พอร์ต 8100 + tunnel ให้เว็บที่ deploy ไว้เรียกเข้ามาได้
  5. เมนู tray "ออก" → ปิด tunnel ก่อน แล้วหยุด server

log: %APPDATA%\\ResumeAI\\logs\\resume_ai.log (เมนู tray "เปิดโฟลเดอร์ log")
"""

import os
import sys
import json
import time
import ctypes
import socket
import logging
import threading
import traceback
import webbrowser
import urllib.request

import bootstrap

bootstrap.setup()   # ต้องมาก่อน import อื่นที่อ่าน key / ใช้ path ของโปรแกรม

import pystray  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from tunnel import PUBLIC_PORT, PublicServerError  # noqa: E402
from version import VERSION  # noqa: E402

logger = logging.getLogger("resume-ai-launcher")

HOST = "127.0.0.1"   # ห้ามเป็น 0.0.0.0 — กันคนอื่นในวง LAN (เช่นห้องแล็บ) เรียก API ด้วย key ของเรา
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
UI_URL = f"{BASE_URL}/"
APP_NAME = bootstrap.APP_NAME
STARTUP_TIMEOUT = 60   # วินาที — รอ server หน้าเว็บเปิด (ยังไม่รวมเวลาโหลดโมเดล)

_state = {"ready": False, "servers": {}, "tunnel": None, "icon": None}
_public_lock = threading.Lock()


def _message_box(text: str, title: str = APP_NAME, error: bool = True):
    """แจ้งเตือนแบบหน้าต่าง Windows (ไม่ต้องพึ่ง tkinter / เรียกจาก thread ไหนก็ได้)"""
    (logger.error if error else logger.info)(f"[{title}] {text}")
    if sys.platform == "win32":
        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x10000)  # MB_SETFOREGROUND


def _notify(text: str):
    icon = _state["icon"]
    if icon is None:
        return
    try:
        icon.notify(text, APP_NAME)
    except Exception:   # notify ไม่รองรับในบาง backend / Windows ปิดการแจ้งเตือนไว้
        pass


# ============================================
# เช็คว่ามีตัวรันอยู่แล้วไหม
# ============================================
def _our_status(timeout: float = 1.5) -> dict | None:
    """คืน /api/status ถ้าพอร์ต 8000 เป็นของ Resume AI เอง ไม่งั้น None"""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data if data.get("app") == "resume-ai" else None
    except Exception:
        return None


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def _port_busy_message(port: int) -> str:
    return (f"เปิดโปรแกรมไม่ได้: พอร์ต {port} ถูกโปรแกรมอื่นใช้งานอยู่\n\n"
            f"วิธีแก้: ปิดโปรแกรมอื่นที่อาจใช้พอร์ตนี้ (เช่น โปรแกรมพัฒนาเว็บ) หรือรีสตาร์ทเครื่อง "
            f"แล้วเปิด {APP_NAME} ใหม่อีกครั้ง\n\nถ้ายังไม่ได้ ให้ส่งไฟล์ log ในโฟลเดอร์นี้ให้ผู้ดูแล:\n{bootstrap.LOG_DIR}")


_mutex_handle = None


def _acquire_single_instance() -> bool:
    """named mutex ของ Windows — จับกรณีเปิดซ้ำระหว่างที่ตัวแรกยังไม่ทันเปิดพอร์ต"""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\ResumeAI_API_single_instance")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _handle_existing_instance() -> bool:
    """คืน True ถ้าควรจบตัวใหม่นี้ (มีตัวรันอยู่แล้ว หรือพอร์ตถูกโปรแกรมอื่นใช้)"""
    first_instance = _acquire_single_instance()

    if not first_instance:
        # ตัวแรกอาจยังเปิดพอร์ตไม่ทัน — รอสักครู่แล้วเปิดเบราว์เซอร์ให้เฉยๆ
        for _ in range(20):
            if _our_status():
                break
            time.sleep(0.5)
        webbrowser.open(UI_URL)
        return True

    if _port_in_use(PORT):
        if _our_status():
            webbrowser.open(UI_URL)   # ไม่น่าเกิด (mutex จับไว้แล้ว) แต่ถ้าเป็นของเราก็แค่เปิดหน้าเว็บ
        else:
            _message_box(_port_busy_message(PORT))
        return True
    return False


# ============================================
# server + tray
# ============================================
def create_icon_image(ready: bool):
    color = (15, 110, 92) if ready else (140, 140, 140)
    img = Image.new("RGB", (64, 64), color=color)
    d = ImageDraw.Draw(img)
    d.text((18, 24), "AI", fill=(255, 255, 255))
    return img


_TUNNEL_TOOLTIP = {
    "connected": "เว็บเชื่อมต่อแล้ว",
    "connecting": "กำลังเชื่อมเว็บ…",
    "reconnecting": "เว็บหลุด กำลังต่อใหม่…",
    "error": "เชื่อมเว็บไม่สำเร็จ",
}


def _set_status(icon, ready: bool, tunnel_state: str | None = None):
    icon.icon = create_icon_image(ready)
    title = f"{APP_NAME} v{VERSION} — {'พร้อมใช้งาน' if ready else 'กำลังเตรียมระบบ…'}"
    # สถานะการเชื่อมเว็บโชว์เฉพาะตอนเปิดใช้ส่วนขั้นสูง — ไม่ได้ตั้งไว้ = ไม่พูดถึงเลย
    if ready and tunnel_state in _TUNNEL_TOOLTIP:
        title += f" · {_TUNNEL_TOOLTIP[tunnel_state]}"
    icon.title = title[:127]   # tooltip ของ Windows ยาวได้ไม่เกิน 128 ตัวอักษร


def _fail(icon, text: str):
    _message_box(text)
    icon.stop()
    os._exit(1)


def _start_server(name: str, asgi_app, port: int):
    import uvicorn

    # log_config=None: ไม่ให้ uvicorn ตั้ง handler เอง → log ไปที่ root logger (ไฟล์ log ที่ซ่อน key แล้ว)
    server = uvicorn.Server(uvicorn.Config(asgi_app, host=HOST, port=port, log_level="info", log_config=None))
    thread = threading.Thread(target=server.run, name=f"uvicorn-{port}", daemon=True)
    thread.start()
    _state["servers"][name] = (server, thread)
    return server, thread


def _wait_started(server, thread, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.1)
    return False


def ensure_public_server():
    """เปิด server พอร์ต public (สำหรับ ngrok) ครั้งแรกที่ต้องใช้ — tunnel.manager เรียกก่อนต่อทุกครั้ง"""
    with _public_lock:
        existing = _state["servers"].get("public")
        if existing and existing[1].is_alive():
            return
        if not _state["ready"]:
            raise PublicServerError("รอโปรแกรมโหลดโมเดลให้เสร็จก่อน แล้วจะเชื่อมต่อให้เอง")
        if _port_in_use(PUBLIC_PORT):
            raise PublicServerError(f"พอร์ต {PUBLIC_PORT} ถูกโปรแกรมอื่นใช้อยู่ — ปิดโปรแกรมนั้นหรือรีสตาร์ทเครื่อง "
                                    f"แล้วระบบจะลองเชื่อมต่อใหม่เอง")
        from desktop_app import public_app
        server, thread = _start_server("public", public_app, PUBLIC_PORT)
        if not _wait_started(server, thread, 15):
            raise PublicServerError(f"เปิดพอร์ต {PUBLIC_PORT} สำหรับเชื่อมเว็บไม่สำเร็จ — ดูรายละเอียดในไฟล์ log")


def _start_backend(icon):
    """รันใน thread แยกจาก tray: เปิดหน้าเว็บ → เปิดเบราว์เซอร์ → โหลดโมเดล → (ขั้นสูง) tunnel"""
    try:
        import desktop_app   # เบา: FastAPI + หน้าตั้งค่า ยังไม่โหลดโมเดล
        import tunnel
    except Exception:
        logger.exception("เปิดหน้าเว็บไม่สำเร็จ")
        _fail(icon, f"เปิดโปรแกรมไม่สำเร็จ\n\nกรุณาส่งไฟล์ log ในโฟลเดอร์นี้ให้ผู้ดูแล:\n{bootstrap.LOG_DIR}")
        return

    server, thread = _start_server("local", desktop_app.app, PORT)
    if not _wait_started(server, thread, STARTUP_TIMEOUT):
        # เช่น พอร์ตโดนแย่งไประหว่างเปิด หรือ uvicorn ขาด module (hiddenimports) ใน exe
        _fail(icon, _port_busy_message(PORT) if _port_in_use(PORT) else
              f"เปิดหน้าเว็บไม่สำเร็จ\n\nกรุณาส่งไฟล์ log ในโฟลเดอร์นี้ให้ผู้ดูแล:\n{bootstrap.LOG_DIR}")
        return
    webbrowser.open(UI_URL)

    started = time.time()
    try:
        desktop_app.load_core()
    except BaseException:
        logger.error("โหลดโมเดลไม่สำเร็จ:\n" + traceback.format_exc())
        _fail(icon, "โหลดโมเดล AI ไม่สำเร็จ\n\nลองปิดแล้วเปิดโปรแกรมใหม่ ถ้ายังไม่ได้ให้ส่งไฟล์ log "
                    f"ในโฟลเดอร์นี้ให้ผู้ดูแล:\n{bootstrap.LOG_DIR}")
        return
    logger.info(f"พร้อมใช้งาน (โหลดโมเดล {time.time() - started:.1f} วินาที)")

    _state["ready"] = True
    _state["tunnel"] = tunnel.manager
    tunnel.manager.start(on_change=lambda st: _set_status(icon, True, st["state"]),
                         before_connect=ensure_public_server)
    _set_status(icon, True, tunnel.manager.status()["state"])
    _notify("พร้อมใช้งานแล้ว — วิเคราะห์เรซูเม่ได้ในหน้าเว็บ")


def open_browser(icon, item):
    webbrowser.open(UI_URL)


def open_log_folder(icon, item):
    os.makedirs(bootstrap.LOG_DIR, exist_ok=True)
    os.startfile(bootstrap.LOG_DIR)  # type: ignore[attr-defined]


def quit_app(icon, item):
    # ปิด tunnel ก่อน (backend บน Render จะได้ไม่ส่ง request เข้ามาระหว่างที่ server กำลังปิด)
    if _state["tunnel"] is not None:
        _state["tunnel"].stop(timeout=5)
    for server, _ in _state["servers"].values():
        server.should_exit = True
    for _, thread in _state["servers"].values():
        thread.join(timeout=3)   # รอ server ปิดตัวเอง (ปิด connection ที่ค้าง) ไม่เกิน 3 วินาที
    logger.info("ปิดโปรแกรม")
    icon.stop()
    os._exit(0)


def main():
    logger.info(f"เปิด {APP_NAME} v{VERSION} (frozen={bootstrap.FROZEN})")
    if _handle_existing_instance():
        return

    menu = pystray.Menu(
        pystray.MenuItem("เปิดหน้าเว็บ", open_browser, default=True),   # default = ดับเบิลคลิกไอคอน
        pystray.MenuItem("เปิดโฟลเดอร์ log", open_log_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("ออก", quit_app),
    )
    icon = pystray.Icon("resume_ai", create_icon_image(False), "", menu)
    _state["icon"] = icon
    _set_status(icon, False)

    def setup(icon):
        icon.visible = True
        _notify("กำลังเปิด Resume AI… เบราว์เซอร์จะเปิดให้เอง (ครั้งแรกเตรียมระบบประมาณ 1 นาที)")
        threading.Thread(target=_start_backend, args=(icon,), daemon=True).start()

    icon.run(setup=setup)


if __name__ == "__main__":
    main()
