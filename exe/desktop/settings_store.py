"""
เก็บ/อ่านค่าตั้งค่าที่ผู้ใช้กรอกผ่านหน้าเว็บ (หน้า "ตั้งค่า")
  - API key   → %APPDATA%\\ResumeAI\\.env         (ความลับ)
  - โมเดลที่เลือก + active provider → %APPDATA%\\ResumeAI\\config.json  (ไม่ใช่ความลับ แยกไฟล์จาก key)
  - สวิตช์ "อ่านสกิลจากกราฟิกในเรซูเม่" → config.json (visual_skill_extraction)
  - การเชื่อมกับเว็บที่ deploy ไว้: AI_SERVICE_TOKEN + NGROK_AUTHTOKEN ใน .env, สวิตช์ tunnel ใน config.json
และดึงรายชื่อโมเดลจาก API ของแต่ละค่าย (ใช้ตอนตรวจ key / เปลี่ยนโมเดล)

ทุกฟังก์ชันที่เปลี่ยนค่า จะอัปเดต os.environ ทันที — llm_providers.py / pdf_extraction.py อ่านค่าจาก os.environ
ทุก request (key, VISUAL_SKILL_EXTRACTION, VISION_MODEL_NAME) และ app.py อ่าน DEFAULT_MODEL_PROVIDER /
<PROVIDER>_MODEL_NAME ตอนไม่ได้ระบุใน request → เปลี่ยนในหน้าตั้งค่าแล้วมีผลทันทีโดยไม่ต้องรีสตาร์ท exe

กฎความปลอดภัย: ห้ามคืน/print/log key เต็มเด็ดขาด — ใช้ mask_key() / scrub_secrets() เสมอ
"""

import os
import re
import json
import secrets
import tempfile
import threading

from dotenv import dotenv_values, load_dotenv

from path_utils import get_writable_config_path
from error_utils import PROVIDER_LABELS, classify_error, describe_error, mask_key, scrub_secrets  # noqa: F401

ENV_PATH = get_writable_config_path()
CONFIG_DIR = os.path.dirname(ENV_PATH)
CONFIG_JSON_PATH = os.path.join(CONFIG_DIR, "config.json")

PROVIDERS = ("gemini", "openai", "claude")

# ชื่อตัวแปรต้องตรงกับที่ llm_providers.py อ่าน
ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

# รุ่นที่ใช้ทดสอบในเล่ม — ติด ★ แนะนำ (ถ้าไม่อยู่ในลิสต์ที่ดึงมา จะหาตัวทดแทน ดู _pick_recommended)
RECOMMENDED_MODELS = {
    "gemini": "gemini-3.6-flash",
    "openai": "gpt-5.6-luna",
    "claude": "claude-sonnet-5",
}

# หน้าขอ key ของแต่ละค่าย + คำอธิบายสั้นๆ (แสดงในหน้าตั้งค่าครั้งแรก)
KEY_HELP = {
    "gemini": {
        "url": "https://aistudio.google.com/apikey",
        "steps": "เข้าสู่ระบบด้วยบัญชี Google → กด \"Create API key\" → กดคัดลอก แล้วนำมาวางในช่องด้านล่าง "
                 "(ใช้ฟรีได้ แต่มีโควตาจำกัดต่อนาที/ต่อวัน)",
    },
    "openai": {
        "url": "https://platform.openai.com/api-keys",
        "steps": "เข้าสู่ระบบ OpenAI → กด \"Create new secret key\" → คัดลอก key (ขึ้นต้นด้วย sk-) "
                 "ต้องเติมเครดิตในบัญชีก่อนจึงจะใช้ได้",
    },
    "claude": {
        "url": "https://console.anthropic.com/settings/keys",
        "steps": "เข้าสู่ระบบ Anthropic Console → กด \"Create Key\" → คัดลอก key (ขึ้นต้นด้วย sk-ant-) "
                 "ต้องเติมเครดิตในบัญชีก่อนจึงจะใช้ได้",
    },
}

# token ลับที่ backend (Render) ต้องส่งมาใน header X-AI-Token ตอนเรียก /analyze ผ่าน tunnel
SERVICE_TOKEN_ENV = "AI_SERVICE_TOKEN"
NGROK_AUTHTOKEN_ENV = "NGROK_AUTHTOKEN"

# env ที่ app.py / pdf_extraction.py / llm_providers.py อ่าน — ตั้งจาก config.json ใน apply_config_to_env()
DEFAULT_PROVIDER_ENV = "DEFAULT_MODEL_PROVIDER"
VISUAL_ENV = "VISUAL_SKILL_EXTRACTION"
VISION_MODEL_ENV = "VISION_MODEL_NAME"

LIST_MODELS_TIMEOUT = 10  # วินาที

_lock = threading.Lock()


# ============================================
# โหลดค่าตอนเริ่มโปรแกรม
# ============================================
def load_env_files():
    """โหลด key จาก %APPDATA%\\ResumeAI\\.env เข้า os.environ แบบระบุ path ชัดเจน
    (ไฟล์นี้คือที่หน้าเว็บบันทึก จึงให้ชนะค่าอื่น) — ต้องเรียกก่อน import llm_providers
    ตอนรันแบบ dev ไม่ต้องทำอะไรเพิ่ม: llm_providers.load_dotenv() จะอ่าน .env ในโฟลเดอร์โปรเจกต์ให้เอง
    แบบไม่ทับค่าที่โหลดจากตรงนี้"""
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH, override=True)


def apply_config_to_env():
    """ตั้ง env ที่โค้ด AI อ่าน ให้ตรงกับหน้าตั้งค่า (เรียกตอนเริ่มโปรแกรม และหลังบันทึกทุกครั้ง)"""
    config = _read_config()
    os.environ[DEFAULT_PROVIDER_ENV] = get_active_provider()
    for p in PROVIDERS:
        name = f"{p.upper()}_MODEL_NAME"   # ต้องตรงกับ app.default_model_env()
        model = config["models"].get(p)
        if model:
            os.environ[name] = model
        else:
            os.environ.pop(name, None)
    os.environ[VISUAL_ENV] = "true" if is_visual_enabled() else "false"
    # โมเดล vision = โมเดล Gemini ที่เลือกไว้ (ไม่ได้เลือก = ใช้ default ใน llm_providers)
    if config["models"].get("gemini"):
        os.environ[VISION_MODEL_ENV] = config["models"]["gemini"]
    else:
        os.environ.pop(VISION_MODEL_ENV, None)


# ============================================
# เขียนไฟล์แบบ atomic: เขียน temp ในโฟลเดอร์เดียวกัน แล้ว os.replace ทับ
# (ปิดโปรแกรมกลางคันก็ไม่ทำให้ไฟล์เดิมเสีย)
# ============================================
def _atomic_write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _read_env_file() -> dict:
    if not os.path.exists(ENV_PATH):
        return {}
    return {k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None}


def _write_env_file(values: dict):
    _atomic_write(ENV_PATH, "".join(f"{k}={v}\n" for k, v in values.items() if v))


def _set_env_value(name: str, value: str | None):
    """เขียน/ลบค่าเดียวใน .env แล้วอัปเดต os.environ ให้ตรงกัน (เรียกขณะถือ _lock)"""
    env_values = _read_env_file()
    if value:
        env_values[name] = value
    else:
        env_values.pop(name, None)
    _write_env_file(env_values)
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def _read_config() -> dict:
    try:
        with open(CONFIG_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("models", {})
            return data
    except (OSError, ValueError):
        pass
    return {"active_provider": None, "models": {}}


def _write_config(config: dict):
    _atomic_write(CONFIG_JSON_PATH, json.dumps(config, ensure_ascii=False, indent=2))


# ============================================
# อ่านสถานะ
# ============================================
def is_configured(provider: str) -> bool:
    return bool(os.environ.get(ENV_KEYS[provider]))


def get_saved_model(provider: str) -> str | None:
    return _read_config()["models"].get(provider)


def get_active_provider() -> str:
    """active ตาม config.json ถ้ายังมี key อยู่ ไม่งั้น Gemini ถ้ามี key (Kappa storytelling สูงสุดในเล่ม)
    ไม่งั้นตัวแรกที่มี key ถ้าไม่มี key เลย คืน gemini"""
    active = _read_config().get("active_provider")
    if active in PROVIDERS and is_configured(active):
        return active
    for p in PROVIDERS:  # gemini อยู่ลำดับแรกอยู่แล้ว
        if is_configured(p):
            return p
    return "gemini"


def is_visual_enabled() -> bool:
    return bool(_read_config().get("visual_skill_extraction", True))


def visual_status() -> dict:
    """สถานะส่วน "อ่านสกิลจากกราฟิก" สำหรับหน้าตั้งค่า/หน้าผลลัพธ์ — ฟีเจอร์นี้ใช้ Gemini เสมอ"""
    enabled = is_visual_enabled()
    has_gemini = is_configured("gemini")
    note = None
    if enabled and not has_gemini:
        note = ("ส่วนนี้ใช้ Gemini เสมอ ไม่ว่าจะเลือกค่าย AI ไหนไว้ — ตอนนี้ยังไม่มี Gemini API key "
                "ระบบจึงข้ามขั้นนี้ไป (การวิเคราะห์ส่วนอื่นยังทำงานปกติ) ใส่ Gemini key ในหน้าตั้งค่าเพื่อเปิดใช้")
    return {
        "enabled": enabled,
        "gemini_configured": has_gemini,
        "active": enabled and has_gemini,
        "model": _read_config()["models"].get("gemini"),
        "note": note,
    }


def get_settings_summary() -> dict:
    config = _read_config()
    active = get_active_provider()
    providers = []
    for p in PROVIDERS:
        providers.append({
            "id": p,
            "label": PROVIDER_LABELS[p],
            "configured": is_configured(p),
            "masked_key": mask_key(os.environ.get(ENV_KEYS[p])),
            "model": config["models"].get(p),
            "recommended_model": RECOMMENDED_MODELS[p],
            "key_help": KEY_HELP[p],
        })
    return {
        "active_provider": active if is_configured(active) else None,
        "providers": providers,
        "visual": visual_status(),
    }


# ============================================
# บันทึก / ลบ
# ============================================
def save_settings(provider: str, model: str | None, api_key: str | None = None, make_active: bool = False):
    """api_key=None = ใช้ key เดิมที่บันทึกไว้ (กรณีเปลี่ยนแค่โมเดล), model=None = คงโมเดลเดิม"""
    with _lock:
        if api_key:
            _set_env_value(ENV_KEYS[provider], api_key)
        elif not is_configured(provider):
            raise ValueError(f"ยังไม่มี API key ของ {PROVIDER_LABELS[provider]} — ต้องใส่ key ก่อน")

        config = _read_config()
        if model:
            config["models"][provider] = model
        current_active = config.get("active_provider")
        if make_active or not (current_active in PROVIDERS and is_configured(current_active)):
            config["active_provider"] = provider
        _write_config(config)
        apply_config_to_env()


def delete_settings(provider: str):
    with _lock:
        _set_env_value(ENV_KEYS[provider], None)

        config = _read_config()
        config["models"].pop(provider, None)
        if config.get("active_provider") == provider:
            config["active_provider"] = None
        _write_config(config)
        apply_config_to_env()


def set_visual_enabled(enabled: bool):
    with _lock:
        config = _read_config()
        config["visual_skill_extraction"] = bool(enabled)
        _write_config(config)
        apply_config_to_env()


# ============================================
# เชื่อมกับเว็บที่ deploy ไว้ (ngrok tunnel + token ลับ)
# ============================================
def ensure_service_token() -> str:
    """สุ่ม AI_SERVICE_TOKEN ครั้งแรกที่เปิดโปรแกรม แล้วใช้ค่าเดิมตลอด (เปลี่ยนได้ด้วย regenerate_service_token)"""
    with _lock:
        token = os.environ.get(SERVICE_TOKEN_ENV)
        if not token:
            token = secrets.token_urlsafe(32)
            _set_env_value(SERVICE_TOKEN_ENV, token)
        return token


def get_service_token() -> str | None:
    return os.environ.get(SERVICE_TOKEN_ENV) or None


def regenerate_service_token() -> str:
    with _lock:
        token = secrets.token_urlsafe(32)
        _set_env_value(SERVICE_TOKEN_ENV, token)
        return token


def get_ngrok_authtoken() -> str | None:
    return os.environ.get(NGROK_AUTHTOKEN_ENV) or None


def set_ngrok_authtoken(authtoken: str | None):
    """ใส่ authtoken ใหม่ = ตั้งใจจะเชื่อมต่อ → เปิดสวิตช์ให้ด้วย / ลบ authtoken = ปิดสวิตช์"""
    with _lock:
        _set_env_value(NGROK_AUTHTOKEN_ENV, authtoken)
        config = _read_config()
        config["tunnel_enabled"] = bool(authtoken)
        _write_config(config)


def is_tunnel_enabled() -> bool:
    # ปิดเป็นค่าเริ่มต้น — อาจารย์ใช้หน้าวิเคราะห์ในเครื่องเป็นหลัก การเชื่อมเว็บเป็นส่วนขั้นสูง
    return bool(_read_config().get("tunnel_enabled", False))


def set_tunnel_enabled(enabled: bool):
    with _lock:
        config = _read_config()
        config["tunnel_enabled"] = bool(enabled)
        _write_config(config)


# ============================================
# ดึงรายชื่อโมเดล
# ============================================
class ModelListError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


# llm_providers เรียก OpenAI ผ่าน chat.completions → ตัดรุ่นที่ไม่ใช่แชต/ข้อความ และรุ่นที่ใช้ chat.completions ไม่ได้
# (instruct = completions แบบเก่า, codex = responses API อย่างเดียว, live = เสียงแบบ realtime)
_OPENAI_EXCLUDE = (
    "embedding", "tts", "whisper", "transcribe", "dall-e", "image", "audio", "realtime", "live",
    "moderation", "sora", "davinci", "babbage", "search", "computer-use", "instruct", "codex",
)
# Gemini: รุ่นที่รองรับ generateContent แต่ไม่ได้ตอบเป็นข้อความ/ใช้งานเฉพาะทาง
_GEMINI_EXCLUDE = (
    "tts", "image", "transcribe", "lyria", "banana", "computer-use", "robotics",
    "deep-research", "antigravity", "customtools",
)


def _gemini_version_key(model_id: str):
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", model_id)
    major, minor = (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    is_preview = any(w in model_id for w in ("preview", "exp"))
    return (major, minor, not is_preview, -len(model_id))


def _list_gemini(api_key: str) -> list[dict]:
    import google.generativeai as genai
    import google.ai.generativelanguage as glm

    # สร้าง client แยกต่างหาก ไม่ใช้ genai.configure() เพราะเป็นค่า global
    # (ตรวจ key ใหม่ระหว่างที่มีการวิเคราะห์ค้างอยู่ จะได้ไม่ไปทับ key ที่กำลังใช้)
    client = glm.ModelServiceClient(client_options={"api_key": api_key}, transport="rest")
    models = []
    for m in genai.list_models(client=client, request_options={"timeout": LIST_MODELS_TIMEOUT, "retry": None}):
        model_id = m.name.removeprefix("models/")
        supports_text = "generateContent" in (m.supported_generation_methods or [])
        if supports_text and not any(w in model_id for w in _GEMINI_EXCLUDE):
            models.append({"id": model_id, "label": m.display_name or model_id})
    models.sort(key=lambda x: _gemini_version_key(x["id"]), reverse=True)
    return models


def _list_openai(api_key: str) -> list[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=LIST_MODELS_TIMEOUT, max_retries=0)
    data = [m for m in client.models.list().data if not any(w in m.id.lower() for w in _OPENAI_EXCLUDE)]
    data.sort(key=lambda m: getattr(m, "created", 0) or 0, reverse=True)
    return [{"id": m.id, "label": m.id} for m in data]


def _list_claude(api_key: str) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=LIST_MODELS_TIMEOUT, max_retries=0)
    data = list(client.models.list(limit=1000))
    data.sort(key=lambda m: str(getattr(m, "created_at", "")), reverse=True)
    return [{"id": m.id, "label": getattr(m, "display_name", None) or m.id} for m in data]


_LISTERS = {"gemini": _list_gemini, "openai": _list_openai, "claude": _list_claude}


def _pick_recommended(provider: str, models: list[dict]) -> str | None:
    """คืน id ที่ควรติด ★ (models เรียงจากใหม่ไปเก่าแล้ว) — OpenAI ไม่ติด ★ ถ้าไม่เจอรุ่นในเล่ม"""
    ids = [m["id"] for m in models]
    if RECOMMENDED_MODELS[provider] in ids:
        return RECOMMENDED_MODELS[provider]
    family = {"gemini": "flash", "claude": "sonnet"}.get(provider)
    if not family:
        return None
    candidates = [i for i in ids if family in i]
    # Gemini: เลี่ยง flash รุ่นย่อยเฉพาะทาง (lite/image/tts/live) ถ้ามีตัวหลักให้เลือก
    plain = [i for i in candidates if not any(w in i for w in ("lite", "image", "tts", "live", "audio"))]
    return (plain or candidates or [None])[0]


def list_models(provider: str, api_key: str) -> list[dict]:
    """คืน [{id, label, recommended}] โดยตัว ★ อยู่บนสุด — โยน ModelListError ถ้าดึงไม่ได้"""
    if not api_key:
        raise ModelListError("no_key", f"ยังไม่ได้ตั้ง API key ของ {PROVIDER_LABELS[provider]}")
    try:
        models = _LISTERS[provider](api_key)
    except Exception as e:
        kind = classify_error(e)
        label = PROVIDER_LABELS[provider]
        if kind == "invalid_key":
            raise ModelListError(kind, f"API key ของ {label} ไม่ถูกต้อง — ตรวจว่าคัดลอกมาครบทุกตัวอักษร และยังไม่ถูกยกเลิก")
        if kind == "network":
            raise ModelListError(kind, f"เชื่อมต่อ {label} ไม่ได้ (อินเทอร์เน็ตมีปัญหาหรือหมดเวลารอ {LIST_MODELS_TIMEOUT} วินาที) — ลองใหม่อีกครั้ง")
        raise ModelListError("other", f"ดึงรายชื่อโมเดลของ {label} ไม่สำเร็จ: {scrub_secrets(str(e), (api_key,))[:300]}")

    if not models:
        raise ModelListError("other", f"key นี้ใช้ได้ แต่ไม่พบโมเดลที่ใช้วิเคราะห์ข้อความได้เลยใน {PROVIDER_LABELS[provider]}")

    recommended = _pick_recommended(provider, models)
    for m in models:
        m["recommended"] = m["id"] == recommended
    models.sort(key=lambda m: not m["recommended"])  # stable sort: ★ ขึ้นบนสุด ที่เหลือคงลำดับเดิม
    return models
