"""
FastAPI service ที่ห่อ full_analysis_pipeline ให้เรียกผ่าน HTTP ได้
โมเดล SBERT/spaCy/Gemini โหลดครั้งเดียวตอน server start (ไม่โหลดซ้ำทุก request)

วิธีรัน:
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload

ทดสอบ:
    เปิด http://localhost:8000/docs จะได้หน้า Swagger UI ทดสอบ API ได้ทันที
    หรือยิงตรงด้วย curl:
    curl -X POST http://localhost:8000/analyze \
      -H "Content-Type: application/json" \
      -d '{"resume_text": "...", "job_text": "..."}'

ตัวโปรแกรม .exe (โฟลเดอร์ desktop/) ใช้ router + run_analysis จากไฟล์นี้ตรงๆ แล้วเพิ่มหน้าเว็บ/หน้าตั้งค่าเอง
"""

import os
import logging
import requests
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from test_full_pipeline_v4 import full_analysis_pipeline
from pdf_extraction import extract_text_from_pdf_url
from error_utils import describe_error, scrub_secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resume-ai-service")

PROVIDER_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

# ไม่ส่ง model_provider มาใน request → ใช้ env DEFAULT_MODEL_PROVIDER → ถ้าไม่มีก็ "gemini"
# (exe ตั้ง env นี้ตาม provider ที่เลือกไว้ในหน้าตั้งค่า, Docker/HF ไม่ต้องตั้ง = gemini เหมือนเดิม)
DEFAULT_PROVIDER_ENV = "DEFAULT_MODEL_PROVIDER"


def default_model_env(provider: str) -> str:
    """ชื่อ env ของโมเดล default ต่อ provider เช่น GEMINI_MODEL_NAME — ไม่ตั้ง = ใช้ default ใน llm_providers"""
    return f"{provider.upper()}_MODEL_NAME"


def resolve_provider_and_model(model_provider: str | None, model_name: str | None) -> tuple[str, str | None]:
    provider = model_provider or os.environ.get(DEFAULT_PROVIDER_ENV) or "gemini"
    model = model_name or os.environ.get(default_model_env(provider)) or None
    return provider, model


app = FastAPI(title="Resume Screening AI Service")

# เปิด CORS ให้ frontend (Next.js ที่มักรันที่ localhost:3000) เรียกเข้ามาได้
# ตอนขึ้น production ให้เปลี่ยน origin เป็น domain จริงแทน "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# /health กับ /analyze อยู่ใน router แยก เพื่อให้ exe (desktop/desktop_app.py) เอาไปต่อกับ app ของตัวเองได้
router = APIRouter()


@app.on_event("startup")
def check_config():
    # เช็คครบทั้ง 3 ค่าย เพราะ /analyze รองรับ model_provider ได้ทั้ง gemini/openai/claude
    # (ไม่ error หยุด server แค่ warning ไว้ก่อน เผื่อบาง provider ยังไม่ได้ใช้จริง)
    available_providers = []
    for provider, env_key in PROVIDER_ENV_KEYS.items():
        if os.environ.get(env_key):
            logger.info(f"✅ พบ {env_key} แล้ว (provider: {provider})")
            available_providers.append(provider)
        else:
            logger.warning(
                f"⚠️  ไม่พบ {env_key} ใน environment variable — "
                f"เรียก /analyze ด้วย model_provider=\"{provider}\" จะ error ทันที "
                f"(ตั้งค่าใน .env: {env_key}=your_key_here)"
            )

    if not available_providers:
        logger.warning("⚠️  ยังไม่มี provider ไหนพร้อมใช้งานเลย — /analyze จะ error ทุก request")
    else:
        logger.info(f"พร้อมใช้งาน {len(available_providers)}/3 provider: {available_providers} "
                    f"(default: {resolve_provider_and_model(None, None)[0]})")


@app.get("/")
def root():
    return {"message": "Resume Screening AI Service กำลังทำงานอยู่ ไปที่ /docs เพื่อทดสอบ API"}


class AnalyzeRequest(BaseModel):
    resume_text: str | None = None   # แบบเดิม: ส่งข้อความที่สกัดมาแล้ว
    resume_url: str | None = None    # แบบใหม่: ส่ง URL ไฟล์ PDF (เช่น Cloudinary secure_url) ให้ service สกัดเอง
    job_text: str
    job_title: str | None = None      # ชื่อตำแหน่งงานที่เปิดรับ ส่งมาจาก backend ตรงๆ (เช่น post.title)
    faculty_match: str | None = None  # คณะ/สาขาที่ต้องการสำหรับตำแหน่งนี้ ส่งมาจาก backend ตรงๆ (เช่น post.faculty)
    faculty: str | None = None        # ชื่อเรียกอีกแบบของ faculty_match (ส่งตัวไหนก็ได้ — กันค่าหายเงียบถ้า backend ใช้ชื่อนี้)
    model_provider: str | None = None  # "gemini" | "openai" | "claude" — ไม่ระบุ = env DEFAULT_MODEL_PROVIDER หรือ "gemini"
    model_name: str | None = None      # ไม่ระบุ = env <PROVIDER>_MODEL_NAME หรือ default ของ provider นั้น


class AnalyzeResponse(BaseModel):
    matching_score: float
    raw_matching_score: float          # คะแนนดิบจาก SBERT ก่อนโดนหักด้วย faculty/skill penalty
    matching_penalty_multiplier: float  # ตัวคูณรวม (faculty_penalty × skill_penalty) — ดูได้ว่าโดนหักเพราะอะไร
    skill_overlap_ratio: float | None   # สัดส่วนทักษะที่ JD ต้องการแล้ว resume มีจริง — None ถ้าดึง skill จาก JD ไม่ได้เลย
    matching_confidence: float
    resume_quality_score: float  # คะแนนคุณภาพ resume ล้วนๆ ไม่เทียบ JD — โชว์ฝั่งผู้สมัคร
    skills: dict
    skill_extraction_confidence: float
    storytelling_score: str | None
    ai_reason: str | None
    specific_strengths: str | None
    faculty_match: str | None
    recommendation_reason: str | None
    storytelling_confidence: float
    storytelling_provider: str | None
    storytelling_latency_seconds: float | None
    overall_confidence: float
    text_extraction_method: str | None = None    # "text_layer" | "ocr_fallback" | None (ตอนส่ง resume_text ตรงๆ)
    text_extraction_warning: str | None = None   # ไม่ None ถ้าข้อความอาจยังเพี้ยนอยู่บ้างแม้ลอง OCR แล้ว
    visual_skills: list[str] = []        # สกิลที่ดึงได้จากกราฟิกในเรซูเม่ (skill bar/กราฟ %/ดาว/ไอคอน) — [] ถ้าไม่มีหรือส่ง resume_text ตรงๆ
    visual_skills_used: bool = False     # True ถ้ามีสกิลจากกราฟิกถูกต่อท้าย resume_text จริง


@router.get("/health")
def health():
    """เอาไว้ให้ Backend เช็คว่า service นี้ยังมีชีวิตอยู่ไหม ก่อนยิง request จริง"""
    return {"status": "ok"}


class AnalysisError(Exception):
    """kind: "bad_request" | "no_key" | "invalid_key" | "quota" | "model_not_found" | "network" | "other"
    message เป็นภาษาไทย และไม่มี key เต็มหลุดออกไป"""
    def __init__(self, status_code: int, kind: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind
        self.message = message


def run_analysis(resume_text: str, job_text: str, faculty_match: str | None, job_title: str | None,
                 model_provider: str | None, model_name: str | None, extraction: dict | None) -> dict:
    """ส่วนที่ /analyze กับ /analyze-file (ใน exe) ใช้ร่วมกัน — extraction = ผลจาก pdf_extraction (None ถ้าส่ง resume_text ตรงๆ)
    โยน AnalysisError ถ้าวิเคราะห์ไม่สำเร็จ"""
    if not resume_text.strip():
        raise AnalysisError(400, "bad_request", "resume_text ที่ได้ว่างเปล่า")

    provider, model = resolve_provider_and_model(model_provider, model_name)
    try:
        result = full_analysis_pipeline(
            resume_text, job_text,
            required_faculty=faculty_match, job_title=job_title,
            model_provider=provider, model_name=model
        )
    except ValueError as e:
        # provider ที่ระบุมาไม่รู้จัก (พิมพ์ผิด หรือยังไม่รองรับ)
        raise AnalysisError(400, "bad_request", str(e))
    except RuntimeError as e:
        # provider รู้จัก แต่ยังไม่ได้ตั้ง API key ไว้
        raise AnalysisError(503, "no_key", str(e))
    except Exception as e:
        kind, message = describe_error(provider, e, model)
        logger.error(f"วิเคราะห์ไม่สำเร็จ ({provider}/{model}): {scrub_secrets(repr(e))[:500]}")
        raise AnalysisError(500, kind, f"เกิดข้อผิดพลาดระหว่างวิเคราะห์: {message}")

    result["text_extraction_method"] = extraction["method"] if extraction else None
    result["text_extraction_warning"] = extraction["warning"] if extraction else None
    result["visual_skills"] = extraction["visual_skills"] if extraction else []
    result["visual_skills_used"] = extraction["visual_skills_used"] if extraction else False
    return result


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if not req.job_text.strip():
        raise HTTPException(status_code=400, detail="job_text ห้ามว่าง")

    extraction = None

    # หา resume_text จริงที่จะใช้: ถ้าส่ง resume_url มา ให้ดาวน์โหลด+สกัดเอง (pdfplumber → OCR fallback ถ้าจำเป็น
    # รวมถึงดึงสกิลจากกราฟิกถ้ามี — ดู pdf_extraction.extract_text_from_pdf_bytes)
    # ถ้าไม่ส่ง resume_url แต่ส่ง resume_text มาตรงๆ ก็ใช้เลย (รองรับของเดิมไว้ — ไม่มีไฟล์ PDF ให้ตรวจกราฟิก)
    if req.resume_url:
        try:
            extraction = extract_text_from_pdf_url(req.resume_url)
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"ดาวน์โหลด resume_url ไม่สำเร็จ: {str(e)}")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        resume_text = extraction["text"]
    elif req.resume_text:
        resume_text = req.resume_text
    else:
        raise HTTPException(status_code=400, detail="ต้องส่ง resume_text หรือ resume_url อย่างใดอย่างหนึ่ง")

    try:
        return run_analysis(resume_text, req.job_text, req.faculty_match or req.faculty, req.job_title,
                            req.model_provider, req.model_name, extraction)
    except AnalysisError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


app.include_router(router)
