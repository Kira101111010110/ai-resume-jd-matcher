# exe/ — โปรแกรม ResumeAI สำหรับ Windows (.exe + ตัวติดตั้ง)

โฟลเดอร์นี้รวมทุกอย่างของตัวโปรแกรม แยกจาก API หลักที่ root ของ repo (Docker / Hugging Face)

| ส่วน | อยู่ที่ |
|---|---|
| หน้าเว็บในเครื่อง, หน้าตั้งค่า, system tray, build script, ตัวติดตั้ง | [`desktop/`](desktop/) — ดูวิธี build ที่ [`desktop/README.md`](desktop/README.md) |
| โค้ด AI เวอร์ชันที่ exe ใช้ (แก้บั๊กที่ทำให้ exe พังบนเครื่องอื่น, ข้อความ error อ่านง่าย ฯลฯ) | `app.py`, `test_full_pipeline_v4.py`, `pdf_extraction.py`, `llm_providers.py`, `error_utils.py`, `path_utils.py` |
| สคริปต์วิจัยที่เพิ่มมา | `generate_synthetic_resumes.py`, `merge_openai_retest.py`, `run_comparison.py`, `cleaned_hard_final.jsonl` |

ไฟล์ที่เหมือนกับของเดิมที่ root ทุกตัวอักษรไม่ได้ copy มาซ้ำ เช่น เรซูเม่ตัวอย่าง (`../synthetic_resumes/`),
`Dockerfile`, `env.example`, `cleaned_soft.jsonl`, `rebuild_entity_ruler.py` — โปรแกรมอ้างถึงเรซูเม่ตัวอย่างจาก `../synthetic_resumes/` โดยตรง

โมเดล (`resume-jd-matcher-model/`, `skill-extractor-model/`) ใหญ่เกิน git — ดาวน์โหลดจาก Releases `v1.0-models` มาวางไว้ในโฟลเดอร์ `exe/` นี้
