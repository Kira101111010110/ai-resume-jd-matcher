"""
เรซูเม่ตัวอย่างสำหรับปุ่ม "ลองด้วยเรซูเม่ตัวอย่าง" — ใช้รายละเอียดงานเดียวกันทั้งหมด เพื่อให้เห็นว่าผลต่างกันเพราะตัวเรซูเม่
ไฟล์มาจาก synthetic_resumes/ ที่ root ของ repo (นอกโฟลเดอร์ exe/ — ใช้ชุดเดียวกับ API หลัก ไม่ copy ซ้ำ) (ตอน build exe แพ็กไว้ใน samples/ — ดู ResumeAI_API.spec)
"""

import os
import json

from bootstrap import FROZEN, ROOT_DIR, bundle_path

# ROOT_DIR = exe/ — เรซูเม่ตัวอย่างอยู่ที่ synthetic_resumes/ ของ repo (โฟลเดอร์แม่)
SAMPLES_DIR = os.path.join(os.path.dirname(ROOT_DIR), "synthetic_resumes")

JOB_ID = "jd_backend_developer"
JOB_TITLE = "Backend Developer"

# source = path ภายใต้ synthetic_resumes/ (ตอนเป็น exe ไฟล์อยู่ที่ samples/<ชื่อไฟล์>)
SAMPLES = [
    {
        "id": "story",
        "title": "สมชาย — เล่าเรื่องดี",
        "description": "เขียนเป็นเรื่องราว ปัญหา → สิ่งที่ทำ → ผลลัพธ์ มีตัวเลขชัดเจน",
        "source": "pdf/01_it_junior_high_storytelling.pdf",
    },
    {
        "id": "keyword",
        "title": "ธนกร — เขียนเป็นรายการคำ",
        "description": "ลิสต์ทักษะยาวๆ แต่ไม่ได้เล่าว่าทำอะไร ได้ผลอย่างไร",
        "source": "pdf/02_it_senior_keyword_heavy.pdf",
    },
    {
        "id": "visual",
        "title": "Maria — เครื่องมือเป็นโลโก้",
        "description": "หัวข้อ Tools แสดงเป็นโลโก้ (ไม่มีตัวหนังสือ) ระบบอ่านจากภาพด้วย Gemini",
        "source": "visual/C.pdf",
    },
]


def _path(source: str) -> str:
    if FROZEN:
        return bundle_path(os.path.join("samples", os.path.basename(source)))
    return os.path.join(SAMPLES_DIR, source)


def job_text() -> str:
    with open(_path("job_descriptions.json"), encoding="utf-8") as f:
        return json.load(f)[JOB_ID]


def list_samples() -> dict:
    return {
        "job_title": JOB_TITLE,
        "job_text": job_text(),
        "samples": [{k: s[k] for k in ("id", "title", "description")} for s in SAMPLES],
    }


def read_sample(sample_id: str) -> tuple[bytes, str] | None:
    """คืน (pdf_bytes, ชื่อไฟล์) หรือ None ถ้าไม่มี id นี้"""
    for s in SAMPLES:
        if s["id"] == sample_id:
            with open(_path(s["source"]), "rb") as f:
                return f.read(), os.path.basename(s["source"])
    return None


def all_source_files() -> list[str]:
    """ไฟล์ทั้งหมดที่ต้องแพ็กไปกับ exe (path ภายใต้ synthetic_resumes/) — ใช้ใน ResumeAI_API.spec"""
    return ["job_descriptions.json"] + [s["source"] for s in SAMPLES]
