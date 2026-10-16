# -*- coding: utf-8 -*-
"""
สคริปต์ชั่วคราวสำหรับทำตารางเปรียบเทียบก่อน/หลังเปิด VISUAL_SKILL_EXTRACTION
รันไฟล์ A.pdf และ C.pdf ผ่าน /analyze จริง (ผ่าน FastAPI TestClient ซึ่งเรียก endpoint function
เดียวกับที่ uvicorn ใช้ ต่างกันแค่ไม่ผ่าน network layer ของ HTTP server) ด้วย JD เดียวกัน
สลับ VISUAL_SKILL_EXTRACTION=false/true ก่อนแต่ละ request (อ่านจาก os.environ สดทุกครั้งอยู่แล้ว
ใน pdf_extraction._visual_extraction_enabled() ไม่ต้อง restart server)
ต้องมี http.server เสิร์ฟ synthetic_resumes/visual/ ที่พอร์ต 8001 อยู่ก่อน (resume_url ต้องดาวน์โหลดได้จริง)
เช่น จาก root ของ repo: python -m http.server 8001 --directory synthetic_resumes/visual

วิธีรันสคริปต์นี้: ต้องรันจาก root ของ repo เท่านั้น (ไม่ใช่จากใน local_manual_scripts/)
    cd <repo root>
    python local_manual_scripts/run_before_after_comparison.py
เหตุผล: ไฟล์นี้ import app.py ซึ่ง import test_full_pipeline_v4.py ที่โหลดโมเดล SBERT ด้วย relative path
('./resume-jd-matcher-model/...') ที่ผูกกับ working directory ตอนรัน ไม่ใช่ตำแหน่งไฟล์ — เป็นพฤติกรรม
เดิมของ test_full_pipeline_v4.py ไม่ได้แก้ตรงนี้
"""

import os
import sys
import time
import json

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# เพิ่ม root ของ repo เข้า sys.path เพราะไฟล์นี้อยู่ใน local_manual_scripts/ ไม่ใช่ root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

JOB_TEXT = (
    "We are hiring a Full-stack Developer skilled in HTML, CSS, JavaScript, React, "
    "Docker, PostgreSQL, and Figma, responsible for building and deploying web "
    "applications end to end."
)

CASES = [
    ("A.pdf", "false"),
    ("A.pdf", "true"),
    ("C.pdf", "false"),
    ("C.pdf", "true"),
]

rows = []
for filename, flag in CASES:
    os.environ["VISUAL_SKILL_EXTRACTION"] = flag
    payload = {
        "resume_url": f"http://localhost:8001/{filename}",
        "job_text": JOB_TEXT,
        "model_provider": "gemini",
    }
    start = time.perf_counter()
    resp = client.post("/analyze", json=payload)
    elapsed = round(time.perf_counter() - start, 2)
    data = resp.json()
    row = {
        "file": filename,
        "VISUAL_SKILL_EXTRACTION": flag,
        "http_status": resp.status_code,
        "elapsed_seconds": elapsed,
        "matching_score": data.get("matching_score"),
        "raw_matching_score": data.get("raw_matching_score"),
        "skill_overlap_ratio": data.get("skill_overlap_ratio"),
        "resume_hard_skills": data.get("skills", {}).get("hard"),
        "visual_skills": data.get("visual_skills"),
        "visual_skills_used": data.get("visual_skills_used"),
        "recommendation_reason": data.get("recommendation_reason"),
    }
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print("-" * 80)

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "before_after_comparison.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
print(f"บันทึกผลลัพธ์ทั้งหมดไว้ที่ {output_path} แล้ว")
