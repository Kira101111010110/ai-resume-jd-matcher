"""
run_comparison.py
------------------
รัน resume ทุกใบ x job ทุกตำแหน่ง ผ่าน full_analysis_pipeline()
เปรียบเทียบผลลัพธ์ข้าม LLM provider (Gemini / OpenAI / Claude)
ผลลัพธ์ export เป็น CSV ให้เปิดดูใน Excel ได้ทันที

วิธีใช้:
1. วางไฟล์นี้ไว้ในโฟลเดอร์เดียวกับ test_full_pipeline_v4.py และ llm_providers.py
   (ต้อง import full_analysis_pipeline ได้)
2. วางโฟลเดอร์ synthetic_resumes/ (ที่แตกจาก zip) ไว้ในโฟลเดอร์เดียวกันด้วย
   หรือแก้ RESUME_DIR / JOB_JSON_PATH ด้านล่างให้ชี้ path ที่ถูกต้อง
3. แก้ PROVIDERS_TO_TEST ให้เหลือแค่ provider ที่มี API key จริง (ตอนนี้มีแค่ gemini)
4. รัน: python run_comparison.py
5. ผลลัพธ์จะถูกเขียนไปที่ comparison_results.csv ในโฟลเดอร์เดียวกัน
"""

import csv
import json
import time
import traceback
from pathlib import Path

# ---- แก้ import ให้ตรงกับไฟล์จริงของคุณ ----
from test_full_pipeline_v4 import full_analysis_pipeline

# ---------------- ตั้งค่า ----------------
BASE_DIR = Path(__file__).parent
RESUME_DIR = BASE_DIR / "synthetic_resumes" / "txt"
JOB_JSON_PATH = BASE_DIR / "synthetic_resumes" / "job_descriptions.json"
MANIFEST_PATH = BASE_DIR / "synthetic_resumes" / "manifest.csv"
OUTPUT_CSV = BASE_DIR / "comparison_results.csv"

# มี API key ครบทั้ง 3 ค่ายแล้ว -> ทดสอบทั้งหมด
PROVIDERS_TO_TEST = ["gemini", "openai", "claude"]

# ชื่อโมเดลที่ใช้จริงต่อ provider (ต้องตรงกับที่ llm_providers.py คาดหวัง)
MODEL_NAMES = {
    "gemini": "gemini-3.6-flash",
    "openai": "gpt-4o-mini",
    "claude": "claude-sonnet-5",
}

# ดีเลย์ระหว่างการเรียก API แต่ละครั้ง (วินาที) กัน rate limit (429)
DELAY_BETWEEN_CALLS = 1.0


def load_resumes():
    """โหลด resume ทุกใบจากโฟลเดอร์ txt/ พร้อม metadata จาก manifest.csv"""
    resumes = {}
    with open(MANIFEST_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            resume_id = row["id"]
            txt_file = BASE_DIR / "synthetic_resumes" / row["txt_path"]
            with open(txt_file, encoding="utf-8") as tf:
                text = tf.read()
            resumes[resume_id] = {
                "text": text,
                "field": row["field"],
                "level": row["level"],
                "style_note": row["style_note"],
            }
    return resumes


def load_jobs():
    with open(JOB_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    resumes = load_resumes()
    jobs = load_jobs()

    total_runs = len(resumes) * len(jobs) * len(PROVIDERS_TO_TEST)
    print(f"เตรียมรันทั้งหมด {total_runs} ครั้ง "
          f"({len(resumes)} resume x {len(jobs)} job x {len(PROVIDERS_TO_TEST)} provider)")

    fieldnames = [
        "resume_id", "field", "level", "job_id", "provider", "model_name",
        "matching_score", "matching_confidence",
        "hard_skills", "soft_skills", "skill_extraction_confidence",
        "storytelling_score", "ai_reason", "storytelling_confidence",
        "storytelling_latency_seconds", "overall_confidence", "error",
    ]

    run_count = 0
    error_count = 0

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        for resume_id, resume_data in resumes.items():
            for job_id, job_text in jobs.items():
                for provider in PROVIDERS_TO_TEST:
                    run_count += 1
                    print(f"[{run_count}/{total_runs}] {resume_id} x {job_id} "
                          f"({provider})...", end=" ")

                    row = {
                        "resume_id": resume_id,
                        "field": resume_data["field"],
                        "level": resume_data["level"],
                        "job_id": job_id,
                        "provider": provider,
                        "model_name": MODEL_NAMES[provider],
                        "error": "",
                    }

                    try:
                        result = full_analysis_pipeline(
                            resume_data["text"],
                            job_text,
                            model_provider=provider,
                            model_name=MODEL_NAMES[provider],
                        )
                        row["matching_score"] = result.get("matching_score")
                        row["matching_confidence"] = result.get("matching_confidence")
                        row["hard_skills"] = "; ".join(
                            result.get("skills", {}).get("hard", [])
                        )
                        row["soft_skills"] = "; ".join(
                            result.get("skills", {}).get("soft", [])
                        )
                        row["skill_extraction_confidence"] = result.get(
                            "skill_extraction_confidence"
                        )
                        row["storytelling_score"] = result.get("storytelling_score")
                        row["ai_reason"] = result.get("ai_reason")
                        # แก้บั๊ก: ของเดิมดึง "confidence_score" ซึ่งไม่มี key นี้จริงใน pipeline
                        # key จริงคือ "storytelling_confidence" ตามที่ full_analysis_pipeline คืนค่า
                        row["storytelling_confidence"] = result.get("storytelling_confidence")
                        row["storytelling_latency_seconds"] = result.get(
                            "storytelling_latency_seconds"
                        )
                        row["overall_confidence"] = result.get("overall_confidence")
                        print("OK")
                    except Exception as e:
                        error_count += 1
                        row["error"] = f"{type(e).__name__}: {e}"
                        print(f"ERROR: {e}")
                        traceback.print_exc()

                    writer.writerow(row)
                    out_f.flush()  # เขียนทันทีกันสคริปต์ล่มแล้วข้อมูลหาย

                    time.sleep(DELAY_BETWEEN_CALLS)

    print(f"\nเสร็จแล้ว: {run_count} ครั้ง, error {error_count} ครั้ง")
    print(f"ผลลัพธ์อยู่ที่: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
