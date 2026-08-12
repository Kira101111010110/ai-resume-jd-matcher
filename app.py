"""
FastAPI service ที่ห่อ full_analysis_pipeline ให้เรียกผ่าน HTTP ได้
โมเดล SBERT/spaCy/Gemini โหลดครั้งเดียวตอน server start (ไม่โหลดซ้ำทุก request)

วิธีรัน:
    pip install fastapi uvicorn
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload

ทดสอบ:
    เปิด http://localhost:8000/docs จะได้หน้า Swagger UI ทดสอบ API ได้ทันที
    หรือยิงตรงด้วย curl:
    curl -X POST http://localhost:8000/analyze \
      -H "Content-Type: application/json" \
      -d '{"resume_text": "...", "job_text": "..."}'
"""

import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from test_full_pipeline_v4 import full_analysis_pipeline
from pdf_extraction import extract_text_from_pdf_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resume-ai-service")

app = FastAPI(title="Resume Screening AI Service")

# เปิด CORS ให้ frontend (Next.js ที่มักรันที่ localhost:3000) เรียกเข้ามาได้
# ตอนขึ้น production ให้เปลี่ยน origin เป็น domain จริงแทน "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def check_config():
    if not os.environ.get("GEMINI_API_KEY"):
        logger.warning(
            "⚠️  ไม่พบ GEMINI_API_KEY ใน environment variable — "
            "endpoint /analyze จะ error ทันทีเมื่อมี request เข้ามา "
            "ตั้งค่าด้วย: $env:GEMINI_API_KEY=\"your_key_here\" ก่อนรัน uvicorn"
        )
    else:
        logger.info("✅ พบ GEMINI_API_KEY แล้ว")


@app.get("/")
def root():
    return {"message": "Resume Screening AI Service กำลังทำงานอยู่ ไปที่ /docs เพื่อทดสอบ API"}


class AnalyzeRequest(BaseModel):
    resume_text: str | None = None   # แบบเดิม: ส่งข้อความที่สกัดมาแล้ว
    resume_url: str | None = None    # แบบใหม่: ส่ง URL ไฟล์ PDF (เช่น Cloudinary secure_url) ให้ service สกัดเอง
    job_text: str
    model_provider: str = "gemini"   # "gemini" | "openai" | "claude"
    model_name: str | None = None    # ถ้าไม่ระบุ ใช้ default ของ provider นั้น


class AnalyzeResponse(BaseModel):
    matching_score: float
    matching_confidence: float
    skills: dict
    skill_extraction_confidence: float
    storytelling_score: str | None
    ai_reason: str | None
    storytelling_confidence: float
    storytelling_provider: str | None
    storytelling_latency_seconds: float | None
    overall_confidence: float
    text_extraction_method: str | None = None    # "text_layer" | "ocr_fallback" | None (ตอนส่ง resume_text ตรงๆ)
    text_extraction_warning: str | None = None   # ไม่ None ถ้าข้อความอาจยังเพี้ยนอยู่บ้างแม้ลอง OCR แล้ว


@app.get("/health")
def health():
    """เอาไว้ให้ Backend เช็คว่า service นี้ยังมีชีวิตอยู่ไหม ก่อนยิง request จริง"""
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if not req.job_text.strip():
        raise HTTPException(status_code=400, detail="job_text ห้ามว่าง")

    text_extraction_method = None
    text_extraction_warning = None

    # หา resume_text จริงที่จะใช้: ถ้าส่ง resume_url มา ให้ดาวน์โหลด+สกัดเอง (pdfplumber → OCR fallback ถ้าจำเป็น)
    # ถ้าไม่ส่ง resume_url แต่ส่ง resume_text มาตรงๆ ก็ใช้เลย (รองรับของเดิมไว้)
    if req.resume_url:
        try:
            extraction_result = extract_text_from_pdf_url(req.resume_url)
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"ดาวน์โหลด resume_url ไม่สำเร็จ: {str(e)}")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        resume_text = extraction_result["text"]
        text_extraction_method = extraction_result["method"]
        text_extraction_warning = extraction_result["warning"]
    elif req.resume_text:
        resume_text = req.resume_text
    else:
        raise HTTPException(status_code=400, detail="ต้องส่ง resume_text หรือ resume_url อย่างใดอย่างหนึ่ง")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text ที่ได้ว่างเปล่า")

    try:
        result = full_analysis_pipeline(
            resume_text, req.job_text,
            model_provider=req.model_provider, model_name=req.model_name
        )
        result["text_extraction_method"] = text_extraction_method
        result["text_extraction_warning"] = text_extraction_warning
        return result
    except ValueError as e:
        # provider ที่ระบุมาไม่รู้จัก (พิมพ์ผิด หรือยังไม่รองรับ)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # provider รู้จัก แต่ยังไม่ได้ตั้ง API key ไว้
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดระหว่างวิเคราะห์: {str(e)}")
