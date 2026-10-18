"""
server ของหน้าเว็บในเครื่อง (ตัว exe) — เปิดได้ทันทีโดยยังไม่ต้องโหลดโมเดล
แล้ว launcher.py ค่อยเรียก load_core() ใน thread แยก (import app.py ที่ root = จุดที่โหลด SBERT/spaCy จริง)
ระหว่างโหลด หน้าเว็บขึ้นสถานะ "กำลังเตรียมระบบ" และหน้าตั้งค่าใช้งานได้เลย

  app        → 127.0.0.1:8000  หน้าเว็บ + /api/* + /analyze-file (+ /analyze, /health จาก app.py หลังโหลดเสร็จ)
  public_app → 127.0.0.1:8100  /analyze (ต้องมี X-AI-Token) + /health เท่านั้น — ngrok tunnel ชี้มาที่นี่
               (เปิดเฉพาะตอนใส่ ngrok authtoken ไว้ — ดู launcher.ensure_public_server)

ห้ามคืน key เต็มใน response ใด ๆ — ใช้ masked_key เท่านั้น
"""

import os
import sys
import logging
import secrets
import threading
import subprocess

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import samples
import settings_store
import tunnel
from bootstrap import LOG_DIR, bundle_path
from version import VERSION

logger = logging.getLogger("resume-ai-desktop")

STATIC_DIR = bundle_path("static")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# token ลับสำหรับ /analyze ฝั่ง public (สุ่มครั้งแรกแล้วเก็บใน .env)
settings_store.ensure_service_token()

# ============================================
# สถานะการโหลดโมเดล (launcher เรียก load_core)
# ============================================
_core = {"module": None, "error": None, "loading": True}
_core_lock = threading.Lock()


def load_core():
    """import app.py ที่ root (โหลดโมเดลจริง ใช้เวลาเกือบ 1 นาที) แล้วต่อ /analyze + /health เข้ากับทั้งสอง app
    โยน exception ต่อถ้าโหลดไม่สำเร็จ (launcher แสดงข้อความให้ผู้ใช้)"""
    try:
        import app as core
    except BaseException as e:
        with _core_lock:
            _core["loading"] = False
            _core["error"] = f"{type(e).__name__}: {e}"
        raise
    app.include_router(core.router)
    public_app.include_router(core.router)
    core.check_config()
    with _core_lock:
        _core["module"] = core
        _core["loading"] = False
    logger.info("โหลดโมเดลเสร็จแล้ว พร้อมวิเคราะห์")


def _require_core():
    core = _core["module"]
    if core is None:
        if _core["error"]:
            raise _ui_error(500, "load_failed", "โหลดโมเดล AI ไม่สำเร็จ — ปิดโปรแกรม (คลิกขวาไอคอนที่มุมขวาล่าง → ออก) "
                                                "แล้วเปิดใหม่ ถ้ายังไม่ได้ให้ส่งไฟล์ log มาให้ผู้ดูแล")
        raise _ui_error(503, "loading", "ระบบกำลังเตรียมโมเดล AI อยู่ (ประมาณ 1 นาทีหลังเปิดโปรแกรม) — รอสักครู่แล้วกดวิเคราะห์อีกครั้ง")
    return core


def _ui_error(status_code: int, kind: str, message: str):
    return HTTPException(status_code=status_code, detail={"kind": kind, "message": message})


# ============================================
# app (หน้าเว็บในเครื่อง)
# ============================================
app = FastAPI(title="Resume AI (desktop)")

# เหมือน app.py หลัก — เผื่อเรียก /analyze จาก frontend ที่รันบนเครื่องเดียวกันตอนพัฒนา
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# endpoint ของหน้าเว็บ (ตั้งค่า key / อัปโหลดไฟล์) ใช้ได้เฉพาะจากหน้าเว็บที่ server นี้เสิร์ฟเอง
# กันเว็บอื่นที่เปิดอยู่ในเบราว์เซอร์แอบยิงมาที่ 127.0.0.1 (CSRF / DNS rebinding)
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_UI_ONLY_PREFIXES = ("/api/", "/analyze-file")


@app.middleware("http")
async def restrict_ui_endpoints(request: Request, call_next):
    if request.url.path.startswith(_UI_ONLY_PREFIXES):
        host_header = request.headers.get("host") or ""
        host = host_header.rsplit(":", 1)[0]
        origin = request.headers.get("origin")
        # origin ต้องเป็นหน้าเว็บของ server นี้เอง (host+พอร์ตเดียวกัน) — กันเว็บอื่นบน localhost เช่น :3000
        # ที่ CORS อนุญาตไว้ ไม่ให้อ่าน token / แก้ key ได้
        if host not in _LOCAL_HOSTS or (origin and origin.rstrip("/") != f"http://{host_header}"):
            return JSONResponse(status_code=403, content={"detail": "อนุญาตเฉพาะหน้าเว็บบนเครื่องนี้เท่านั้น"})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # 422 ปกติของ FastAPI แนบ "input" (ค่าที่ส่งมา) กลับไปด้วย — สำหรับ /api/settings นั่นคือ API key เต็ม
    # จึงตัด input ทิ้งเฉพาะ path ของหน้าเว็บ ส่วน /analyze เดิมคงรูปแบบเดิมไว้
    if request.url.path.startswith(_UI_ONLY_PREFIXES):
        errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": {
            "kind": "bad_request", "message": "ข้อมูลที่ส่งมาไม่ครบหรือไม่ถูกต้อง", "errors": errors}})
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    # ห้ามโชว์ traceback ในหน้าเว็บ — เขียนลง log (ผ่านการซ่อน key แล้ว) แล้วตอบข้อความไทยแทน
    logger.exception(f"error ที่ไม่คาดคิดใน {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": {
        "kind": "other",
        "message": "เกิดข้อผิดพลาดที่ไม่คาดคิด — ลองใหม่อีกครั้ง ถ้ายังเป็นอยู่ให้กด \"เปิดโฟลเดอร์ log\" แล้วส่งไฟล์ log ให้ผู้ดูแล"}})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/manual", include_in_schema=False)
def manual():
    return FileResponse(os.path.join(STATIC_DIR, "manual.html"))


@app.get("/api/status")
def status():
    """หน้าเว็บ + launcher ใช้เช็คว่าโปรแกรมพร้อมหรือยัง"""
    summary = settings_store.get_settings_summary()
    return {
        "app": "resume-ai",
        "version": VERSION,
        "ready": _core["module"] is not None,
        "loading": _core["loading"],
        "load_failed": _core["error"] is not None,
        "has_key": summary["active_provider"] is not None,
    }


@app.post("/api/open-log-folder")
def open_log_folder():
    os.makedirs(LOG_DIR, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(LOG_DIR)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", LOG_DIR])
    return {"ok": True, "path": LOG_DIR}


# ============================================
# วิเคราะห์ไฟล์ PDF
# ============================================
def _friendly_notices(extraction: dict) -> list[dict]:
    """แปลงผลการอ่านไฟล์เป็นข้อความที่อาจารย์อ่านเข้าใจ (ข้อความเทคนิคเต็มอยู่ใน text_extraction_warning)"""
    notices = []
    warning = extraction.get("warning") or ""
    if extraction.get("method") == "ocr_fallback":
        notices.append({"level": "warn", "text": "ไฟล์นี้อ่านตัวอักษรได้ไม่ครบ (พบบ่อยกับไฟล์จาก Canva) "
                                                 "ระบบใช้การอ่านจากภาพแทน ผลอาจคลาดเคลื่อนเล็กน้อย"})
    elif "OCR fallback ล้มเหลว" in warning:
        notices.append({"level": "warn", "text": "ไฟล์นี้อ่านตัวอักษรได้ไม่ครบ และอ่านจากภาพไม่สำเร็จ "
                                                 "ระบบใช้ข้อความเท่าที่อ่านได้ ผลอาจคลาดเคลื่อน"})
    elif "ลอง OCR แล้ว" in warning:
        notices.append({"level": "warn", "text": "ไฟล์นี้มีตัวอักษรบางส่วนที่อ่านได้ไม่ชัด ผลอาจคลาดเคลื่อนเล็กน้อย"})

    if "ดึงสกิลจากกราฟิกไม่สำเร็จ" in warning:
        if not settings_store.is_configured("gemini"):
            notices.append({"level": "info", "text": "เรซูเม่นี้แสดงทักษะบางส่วนเป็นกราฟิก แต่ยังไม่มี Gemini API key "
                                                     "ระบบจึงข้ามการอ่านส่วนนี้ (ส่วนอื่นวิเคราะห์ตามปกติ) — ใส่ Gemini key "
                                                     "ในหน้าตั้งค่าเพื่อให้อ่านทักษะจากกราฟิกได้"})
        else:
            notices.append({"level": "info", "text": "อ่านทักษะจากกราฟิกในเรซูเม่ไม่สำเร็จในครั้งนี้ "
                                                     "ระบบใช้เฉพาะข้อความในไฟล์ — ลองวิเคราะห์ใหม่อีกครั้งภายหลัง"})
    return notices


def _analyze_pdf_bytes(pdf_bytes: bytes, job_text: str, job_title: str | None, faculty_match: str | None,
                       model_provider: str | None, model_name: str | None) -> dict:
    core = _require_core()
    from pdf_extraction import extract_text_from_pdf_bytes  # ตัวเดียวกับที่ /analyze ใช้กับ resume_url

    if b"%PDF-" not in pdf_bytes[:1024]:  # สเปก PDF ยอมให้มีขยะนำหน้า header ได้ไม่เกิน 1 KB
        raise _ui_error(415, "bad_request", "ไฟล์นี้ไม่ใช่ PDF (หรือไฟล์เสียหาย) — เลือกไฟล์นามสกุล .pdf")
    try:
        extraction = extract_text_from_pdf_bytes(pdf_bytes)
    except Exception as e:
        logger.warning(f"อ่าน PDF ไม่สำเร็จ: {type(e).__name__}: {e}")
        raise _ui_error(422, "extraction",
                        "อ่านข้อความจากไฟล์ PDF นี้ไม่ได้เลย — ไฟล์อาจเป็นภาพสแกนที่ไม่ชัด เสียหาย หรือตั้งรหัสผ่านไว้ "
                        "ลองบันทึกเป็น PDF ใหม่ (เช่น Canva → ดาวน์โหลด → PDF มาตรฐาน) แล้วอัปโหลดอีกครั้ง")

    try:
        result = core.run_analysis(extraction["text"], job_text, faculty_match, job_title,
                                   model_provider, model_name, extraction)
    except core.AnalysisError as e:
        if e.kind == "no_key":
            provider, _ = core.resolve_provider_and_model(model_provider, model_name)
            label = settings_store.PROVIDER_LABELS.get(provider, provider)
            raise _ui_error(e.status_code, e.kind, f"ยังไม่ได้ใส่ API key ของ {label} — ไปที่หน้าตั้งค่าเพื่อใส่ key ก่อน")
        raise _ui_error(e.status_code, e.kind, e.message)
    # ผ่าน AnalyzeResponse ก่อน = field ครบและเหมือน /analyze ทุกอย่าง แล้วเพิ่ม notices
    # (คำอธิบายภาษาคนทั่วไปที่หน้าผลลัพธ์โชว์ก่อน — ข้อความเทคนิคเต็มยังอยู่ใน text_extraction_warning)
    response = core.AnalyzeResponse(**result).model_dump()
    response["notices"] = _friendly_notices(extraction)
    return response


@app.post("/analyze-file")
def analyze_file(
    file: UploadFile = File(...),
    job_text: str = Form(...),
    job_title: str | None = Form(None),
    faculty_match: str | None = Form(None),     # ชื่อเดียวกับ AnalyzeRequest.faculty_match
    faculty: str | None = Form(None),           # ชื่อเรียกอีกแบบ (รับไว้เหมือน /analyze)
    model_provider: str | None = Form(None),    # ไม่ส่ง = ใช้ค่าในหน้าตั้งค่า
    model_name: str | None = Form(None),
):
    """เหมือน /analyze แต่รับไฟล์ PDF ตรงๆ (multipart/form-data) — ใช้จากหน้าเว็บ
    error: detail = {kind, message} (message เป็นภาษาไทยที่บอกว่าต้องทำอะไรต่อ)"""
    try:
        if not job_text.strip():
            raise _ui_error(400, "bad_request", "กรุณากรอกรายละเอียดงาน")
        filename = (file.filename or "").lower()
        if file.content_type not in ("application/pdf", "application/x-pdf", "application/octet-stream") \
                and not filename.endswith(".pdf"):
            raise _ui_error(415, "bad_request", "รับเฉพาะไฟล์ PDF เท่านั้น — เลือกไฟล์นามสกุล .pdf")

        # อ่านเกินขีดจำกัดมา 1 byte เพื่อรู้ว่าไฟล์ใหญ่เกินไหม โดยไม่ต้องอ่านทั้งไฟล์เข้าหน่วยความจำ
        pdf_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(pdf_bytes) > MAX_UPLOAD_BYTES:
            raise _ui_error(413, "bad_request", f"ไฟล์ใหญ่เกิน {MAX_UPLOAD_BYTES // (1024 * 1024)} MB — "
                                                "ลองบีบอัดไฟล์ หรือบันทึก PDF ใหม่แบบความละเอียดต่ำลง")
        return _analyze_pdf_bytes(pdf_bytes, job_text, job_title, faculty_match or faculty,
                                  model_provider or None, model_name or None)
    finally:
        # ไฟล์ที่อัปโหลดเก็บใน SpooledTemporaryFile (ไฟล์ใหญ่จะถูกเขียนลง temp บนดิสก์) — ปิดเพื่อลบทิ้งทันที
        file.file.close()


@app.get("/api/samples")
def get_samples():
    return samples.list_samples()


@app.post("/api/samples/{sample_id}/analyze")
def analyze_sample(sample_id: str):
    found = samples.read_sample(sample_id)
    if not found:
        raise _ui_error(404, "bad_request", "ไม่พบเรซูเม่ตัวอย่างนี้")
    pdf_bytes, _ = found
    return _analyze_pdf_bytes(pdf_bytes, samples.job_text(), samples.JOB_TITLE, None, None, None)


@app.get("/api/samples/{sample_id}/file", include_in_schema=False)
def sample_file(sample_id: str):
    """เปิดดูไฟล์ PDF ตัวอย่างในเบราว์เซอร์"""
    for s in samples.SAMPLES:
        if s["id"] == sample_id:
            return FileResponse(samples._path(s["source"]), media_type="application/pdf")
    raise _ui_error(404, "bad_request", "ไม่พบเรซูเม่ตัวอย่างนี้")


# ============================================
# หน้าตั้งค่า: API key + เลือกโมเดล + อ่านสกิลจากกราฟิก
# ============================================
def _check_provider(provider: str):
    if provider not in settings_store.PROVIDERS:
        raise _ui_error(400, "bad_request", f"ไม่รู้จักค่าย AI '{provider}'")


class ValidateKeyRequest(BaseModel):
    provider: str
    api_key: str


class SaveSettingsRequest(BaseModel):
    provider: str
    model: str | None = None     # ไม่ส่ง/ว่าง = คงโมเดลเดิม (เช่น แค่สลับ active provider)
    api_key: str | None = None   # ไม่ส่ง = ใช้ key เดิม
    make_active: bool = False


class VisualRequest(BaseModel):
    enabled: bool


def _models_response(provider: str, api_key: str):
    try:
        return {"ok": True, "models": settings_store.list_models(provider, api_key), "error": None}
    except settings_store.ModelListError as e:
        return {"ok": False, "models": [], "error": {"kind": e.kind, "message": e.message}}


@app.get("/api/settings")
def get_settings():
    return settings_store.get_settings_summary()


@app.post("/api/settings/validate")
def validate_key(req: ValidateKeyRequest):
    """ตรวจ key ด้วยการดึงรายชื่อโมเดล — ยังไม่บันทึกอะไรทั้งนั้น"""
    _check_provider(req.provider)
    return _models_response(req.provider, req.api_key.strip())


@app.get("/api/settings/{provider}/models")
def get_models(provider: str):
    """ดึงรายชื่อโมเดลด้วย key ที่บันทึกไว้ (ใช้ตอนเปลี่ยนโมเดลโดยไม่ต้องใส่ key ใหม่)"""
    _check_provider(provider)
    return _models_response(provider, os.environ.get(settings_store.ENV_KEYS[provider], ""))


@app.post("/api/settings/save")
def save_settings(req: SaveSettingsRequest):
    _check_provider(req.provider)
    model = (req.model or "").strip() or None
    if req.api_key and not model:
        raise _ui_error(400, "bad_request", "ต้องเลือกโมเดล")
    try:
        settings_store.save_settings(req.provider, model,
                                     api_key=(req.api_key or "").strip() or None,
                                     make_active=req.make_active)
    except ValueError as e:
        raise _ui_error(400, "bad_request", str(e))
    except OSError as e:
        raise _ui_error(500, "other", f"บันทึกไฟล์ตั้งค่าไม่สำเร็จ ({e.strerror}) — ลองปิดโปรแกรมแล้วเปิดใหม่")
    logger.info(f"บันทึกการตั้งค่า {req.provider} (model={model}, key {'ใหม่' if req.api_key else 'เดิม'})")
    return settings_store.get_settings_summary()


@app.delete("/api/settings/{provider}")
def delete_settings(provider: str):
    _check_provider(provider)
    try:
        settings_store.delete_settings(provider)
    except OSError as e:
        raise _ui_error(500, "other", f"ลบการตั้งค่าไม่สำเร็จ ({e.strerror})")
    logger.info(f"ลบการตั้งค่า {provider}")
    return settings_store.get_settings_summary()


@app.post("/api/settings/visual")
def set_visual(req: VisualRequest):
    settings_store.set_visual_enabled(req.enabled)
    logger.info(f"อ่านสกิลจากกราฟิก: {'เปิด' if req.enabled else 'ปิด'}")
    return settings_store.get_settings_summary()


# ============================================
# ขั้นสูง: เชื่อมกับเว็บที่ deploy ไว้ (ngrok tunnel + token ลับ)
# อยู่ที่พอร์ต local เท่านั้น — tunnel ชี้ไปที่ public_app ด้านล่าง ไม่ใช่ app นี้
# ============================================
class NgrokAuthtokenRequest(BaseModel):
    authtoken: str


class TunnelEnabledRequest(BaseModel):
    enabled: bool


def _connection_summary():
    token = settings_store.get_service_token()
    return {
        "tunnel": tunnel.manager.status(),
        "enabled": settings_store.is_tunnel_enabled(),
        "ngrok_configured": bool(settings_store.get_ngrok_authtoken()),
        "ngrok_masked": settings_store.mask_key(settings_store.get_ngrok_authtoken()),
        "service_token_masked": settings_store.mask_key(token),
    }


@app.get("/api/connection")
def get_connection():
    return _connection_summary()


@app.get("/api/connection/service-token")
def get_service_token():
    """token เต็ม — ใช้เฉพาะตอนกดปุ่ม "คัดลอก" ในหน้าตั้งค่า (endpoint นี้ไม่มีใน public_app)"""
    return {"token": settings_store.get_service_token()}


@app.post("/api/connection/service-token/regenerate")
def regenerate_service_token():
    settings_store.regenerate_service_token()
    logger.info("สร้าง AI_SERVICE_TOKEN ใหม่แล้ว — ต้องอัปเดตค่าบน Render ด้วย")
    return _connection_summary()


@app.post("/api/connection/ngrok")
def save_ngrok_authtoken(req: NgrokAuthtokenRequest):
    authtoken = req.authtoken.strip()
    if not authtoken:
        raise _ui_error(400, "bad_request", "กรุณาวาง ngrok authtoken")
    settings_store.set_ngrok_authtoken(authtoken)
    tunnel.manager.apply_settings()
    logger.info("บันทึก ngrok authtoken แล้ว")
    return _connection_summary()


@app.delete("/api/connection/ngrok")
def delete_ngrok_authtoken():
    settings_store.set_ngrok_authtoken(None)
    tunnel.manager.apply_settings()
    logger.info("ลบ ngrok authtoken แล้ว")
    return _connection_summary()


@app.post("/api/connection/enabled")
def set_tunnel_enabled(req: TunnelEnabledRequest):
    settings_store.set_tunnel_enabled(req.enabled)
    tunnel.manager.apply_settings()
    return _connection_summary()


# ============================================
# public_app: สิ่งเดียวที่ tunnel (ngrok) มองเห็น — รันที่ 127.0.0.1:tunnel.PUBLIC_PORT
# request ที่มาทาง ngrok ก็มาจาก 127.0.0.1 เหมือนกัน การแยกพอร์ตจึงเป็นตัวกันไม่ให้คนนอกเข้าถึง
# หน้าตั้งค่า/static ได้ — app นี้มีแค่ /analyze (ต้องมี X-AI-Token) กับ /health อย่างอื่นตอบ 404
# ใช้ router ของ app.py ชุดเดียวกัน (process เดียวกัน ไม่โหลดโมเดลซ้ำ) — ต่อเข้ามาใน load_core()
# ============================================
public_app = FastAPI(title="Resume Screening AI Service (public)", docs_url=None, redoc_url=None, openapi_url=None)


@public_app.middleware("http")
async def require_service_token(request: Request, call_next):
    # ตรวจ token ก่อนอ่าน body — คนที่ไม่มี token ไม่ได้แม้แต่ error validation กลับไป
    if request.url.path == "/analyze":
        expected = settings_store.get_service_token() or ""
        given = request.headers.get("x-ai-token") or ""
        if not expected or not secrets.compare_digest(given.encode(), expected.encode()):
            return JSONResponse(status_code=401, content={"detail": "X-AI-Token ไม่ถูกต้องหรือไม่ได้ส่งมา"})
    return await call_next(request)
