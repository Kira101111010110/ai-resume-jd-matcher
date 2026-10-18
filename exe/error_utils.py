"""
ช่วยแปลง error จาก SDK ของ LLM ทั้ง 3 ค่ายเป็นข้อความภาษาไทยที่อ่านเข้าใจ และซ่อน key ออกจากข้อความ/log
ใช้ทั้ง app.py (API หลัก) และ desktop/ (หน้าตั้งค่าของ exe)

กฎความปลอดภัย: ห้ามคืน/print/log key เต็มเด็ดขาด — ใช้ mask_key() / scrub_secrets() เสมอ
"""

import os
import re

PROVIDER_LABELS = {
    "gemini": "Gemini (Google)",
    "openai": "OpenAI",
    "claude": "Claude (Anthropic)",
}

# ชื่อตัวแปร env ที่เป็นความลับ — scrub_secrets จะแทนค่าพวกนี้ด้วยแบบ mask ทุกครั้งที่เจอในข้อความ
SECRET_ENV_NAMES = (
    "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "AI_SERVICE_TOKEN", "NGROK_AUTHTOKEN",
)

_KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),          # Gemini (แบบเก่า)
    re.compile(r"AQ\.[0-9A-Za-z_\-]{20,}"),          # Gemini (แบบใหม่)
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),            # OpenAI (sk-, sk-proj-) / Anthropic (sk-ant-)
]


def mask_key(key: str | None) -> str | None:
    """6 ตัวแรก + … + 4 ตัวท้าย (key สั้นผิดปกติ ไม่โชว์อะไรเลย กันหลุดเกือบทั้งตัว)"""
    if not key:
        return None
    if len(key) < 16:
        return "••••••"
    return f"{key[:6]}…{key[-4:]}"


def scrub_secrets(text: str, extra_keys: tuple = ()) -> str:
    if not text:
        return text
    known = [os.environ.get(k) for k in SECRET_ENV_NAMES] + list(extra_keys)
    for s in known:
        if s and len(s) >= 6:
            text = text.replace(s, mask_key(s) or "••••••")
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(lambda m: mask_key(m.group(0)) or "••••••", text)
    return text


def classify_error(exc: Exception) -> str:
    """คืน "invalid_key" | "quota" | "model_not_found" | "network" | "other" """
    import requests

    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if not isinstance(status, int):
        status = None
    name = type(exc).__name__
    text = str(exc)

    conn_errors = ()
    try:
        import openai
        import anthropic
        conn_errors = (openai.APIConnectionError, anthropic.APIConnectionError)  # รวม APITimeoutError แล้ว
    except ImportError:
        pass
    try:
        from google.api_core import exceptions as gexc
        conn_errors += (gexc.DeadlineExceeded, gexc.ServiceUnavailable, gexc.RetryError)
    except ImportError:
        pass

    if "API_KEY_INVALID" in text or "API key not valid" in text or status in (401, 403) \
            or name in ("AuthenticationError", "PermissionDeniedError", "Unauthenticated", "PermissionDenied"):
        return "invalid_key"
    if status == 429 or name in ("RateLimitError", "ResourceExhausted"):
        return "quota"
    if status == 404 or name in ("NotFoundError", "NotFound"):
        return "model_not_found"
    if isinstance(exc, conn_errors + (requests.exceptions.RequestException, TimeoutError, ConnectionError)):
        return "network"
    # SDK ของ Google ห่อ error ของ socket ไว้ในข้อความ ไม่ได้โยน exception ชนิดเฉพาะเสมอไป
    lowered = text.lower()
    if any(w in lowered for w in ("getaddrinfo failed", "name resolution", "failed to establish a new connection",
                                  "connection refused", "network is unreachable", "timed out")):
        return "network"
    return "other"


def describe_error(provider: str, exc: Exception, model_name: str | None = None, extra_keys: tuple = ()) -> tuple[str, str]:
    """แปลง error จาก LLM เป็น (kind, ข้อความภาษาไทยที่อ่านเข้าใจ) — ไม่มี key เต็มหลุดออกไป"""
    kind = classify_error(exc)
    label = PROVIDER_LABELS.get(provider, provider)
    if kind == "invalid_key":
        msg = f"API key ของ {label} ใช้ไม่ได้ (ไม่ถูกต้อง หมดอายุ หรือถูกยกเลิก) — ไปที่หน้าตั้งค่าเพื่อเปลี่ยน key"
    elif kind == "quota":
        msg = (f"โควตาการใช้งานของ {label} เต็มแล้ว (429) — รอสักครู่ (ประมาณ 1 นาที) แล้วลองใหม่ "
               f"หรือไปที่หน้าตั้งค่าเพื่อเปลี่ยนโมเดล / เปลี่ยนค่าย AI")
    elif kind == "model_not_found":
        msg = (f"ไม่พบโมเดล \"{model_name or '-'}\" ของ {label} (404 — อาจถูกปลดระวางแล้ว หรือ key นี้ไม่มีสิทธิ์ใช้) "
               f"— ไปที่หน้าตั้งค่าเพื่อเลือกโมเดลใหม่")
    elif kind == "network":
        msg = f"เชื่อมต่อ {label} ไม่ได้ — ตรวจว่าเครื่องต่ออินเทอร์เน็ตอยู่ แล้วลองใหม่อีกครั้ง"
    else:
        detail = scrub_secrets(str(exc), extra_keys)[:300]
        msg = f"เกิดข้อผิดพลาดจาก {label}: {detail}"
    return kind, msg
