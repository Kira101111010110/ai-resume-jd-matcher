# 📄 Intelligent Resume Screening & JD Matching System

> ระบบคัดกรองและประเมินความเหมาะสมของเรซูเม่กับตำแหน่งงาน (Job Description) อัตโนมัติด้วยเทคนิค NLP, Pattern-based Skill Extraction และโมเดลภาษาขนาดใหญ่ (LLM)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![spaCy](https://img.shields.io/badge/spaCy-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![OpenAI / LLM](https://img.shields.io/badge/LLM-Providers-412991?style=for-the-badge&logo=openai&logoColor=white)

---

## 📌 ภาพรวมโครงการ (Project Overview)

โครงการนี้พัฒนาขึ้นเพื่อเพิ่มประสิทธิภาพในการคัดกรองผู้สมัครงานของฝ่ายบุคคล (HR) โดยระบบสามารถดึงข้อความจากไฟล์เรซูเม่ PDF สกัดทักษะทั้ง Hard Skills และ Soft Skills อย่างแม่นยำด้วย Fine-tuned SBERT และ spaCy Entity Ruler และนำมาจับคู่เปรียบเทียบความเข้ากันได้กับ Job Description (JD) ผ่านโมเดล AI เพื่อจัดอันดับและวิเคราะห์จุดเด่น-จุดด้อยของผู้สมัคร

---

## ✨ คุณสมบัติเด่น (Core Features)

* **Automated PDF Text Extraction** — แปลงและสกัดข้อความจากเรซูเม่ไฟล์ PDF รองรับหลากหลายเลย์เอาต์ พร้อม OCR fallback สำหรับไฟล์ที่มีปัญหาฟอนต์ (`pdf_extraction.py`)
* **Visual Skill Extraction** — ตรวจจับกราฟิกแสดงทักษะในเรซูเม่ (skill bar, กราฟวงกลม %, ดาว/จุด rating, ไอคอน-โลโก้เทคโนโลยี) แล้วส่งให้ Gemini vision อ่านชื่อสกิลมาต่อท้ายข้อความอัตโนมัติ ป้องกันไม่ให้สกิลที่เป็นรูปภาพหายไปจากการวิเคราะห์ (`pdf_extraction.py`, `llm_providers.py` — ดูรายละเอียดหัวข้อ [สกัดสกิลจากกราฟิกในเรซูเม่](#️-สกัดสกิลจากกราฟิกในเรซูเม่-visual-skill-extraction) ด้านล่าง)
* **Fine-tuned SBERT Matching** — วัดความเข้ากันได้ระหว่าง Resume กับ JD ด้วย Semantic Similarity (fine-tune จาก `all-mpnet-base-v2`, Spearman correlation 0.357 → 0.850)
* **Accurate Skill Extraction** — สกัดทักษะเฉพาะทาง (Hard Skills & Soft Skills) ด้วยพจนานุกรมคำศัพท์ที่ทำความสะอาดแล้วและ spaCy Entity Ruler (`rebuild_entity_ruler.py`, `cleaned_hard_final2.jsonl`, `cleaned_soft.jsonl`) — `skill_overlap_ratio` เทียบทักษะ resume/JD ด้วยทักษะที่กรองคำทั่วไป (ชื่อตำแหน่งงาน, คำ noise) ออกแล้วทั้ง 2 ฝั่ง เพื่อไม่ให้ตัวเลขสูง/ต่ำเกินจริงจากคำที่ไม่ใช่ทักษะจริง
* **Multi-LLM Provider Integration** — รองรับการประมวลผลและวิเคราะห์ Storytelling ผ่านโมเดลภาษาขนาดใหญ่หลายค่าย (Gemini / OpenAI / Claude) แบบสลับได้ (`llm_providers.py`)
* **Model Comparison & Evaluation** — มีระบบทดสอบและเปรียบเทียบประสิทธิภาพของแต่ละ Pipeline/Provider (`compare_models.py`, `test_full_pipeline_v4.py`)
* **FastAPI Service** — พร้อมเชื่อมต่อใช้งานจริงผ่าน Backend API (`app.py`) รองรับทั้ง `resume_text` และ `resume_url`

---

## 🎯 เลือกวิธีใช้งานที่เหมาะกับคุณ

โปรเจกต์นี้มี 2 วิธีใช้งาน เลือกตามความต้องการ:

| | 💾 ใช้ตัวติดตั้ง (Installer) | 🧑‍💻 รันจากซอร์สโค้ด (Manual) |
|---|---|---|
| เหมาะกับ | ต้องการใช้งาน API ทันที ไม่อยากตั้งค่าอะไรเอง | ต้องการแก้โค้ด, ต่อยอด, หรือรัน pipeline แยกส่วน (fine-tune, rebuild skill dictionary ฯลฯ) |
| ต้องติดตั้ง Python เอง | ❌ ไม่ต้อง | ✅ ต้องมี Python 3.10+ |
| ดูวิธีใช้ | หัวข้อ [ดาวน์โหลดตัวติดตั้ง](#-ดาวน์โหลดตัวติดตั้ง-windows-installer) ด้านล่าง | หัวข้อ [ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน](#-ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน-getting-started) ด้านล่าง |

> **หมายเหตุ:** ไฟล์ส่วนใหญ่ใน repo นี้ (`app.py`, `test_full_pipeline_v4.py`, `llm_providers.py` ฯลฯ) เขียนขึ้นสำหรับรันด้วยคำสั่งในเครื่องโดยตรง (`python -m uvicorn ...`) ซึ่งเป็นวิธีหลักที่ใช้พัฒนาและทดสอบระบบมาตลอด ส่วน `launcher.py` และตัวติดตั้ง `.exe` เป็นสิ่งที่เพิ่มเข้ามาภายหลัง เพื่อให้คนที่ไม่ต้องการยุ่งกับ Python เปิดใช้งาน API ได้สะดวกขึ้นเท่านั้น ไม่ได้แทนที่วิธีเดิม — ถ้าจะพัฒนาต่อหรือแก้ไขโค้ด แนะนำให้ใช้วิธี **รันจากซอร์สโค้ด** ตามปกติ

---

## 💾 ดาวน์โหลดตัวติดตั้ง (Windows Installer)

ไม่อยากตั้งค่า Python เอง? ดาวน์โหลดตัวติดตั้งสำเร็จรูปสำหรับ Windows ได้จากหน้า Releases:

**[⬇️ ดาวน์โหลด ResumeAI_Setup.exe (Releases ล่าสุด)](../../releases/latest)**

ตัวติดตั้งนี้รวม Python, SBERT, spaCy และ dependency ทั้งหมดไว้ให้แล้ว เปิดใช้งานผ่าน system tray icon ไม่ต้องเปิด terminal เอง — ครั้งแรกที่เปิดแอพจะมีหน้าต่างให้กรอก API Key (Gemini / OpenAI / Claude เลือกอย่างน้อย 1 ตัว) โดย key จะถูกเก็บไว้ในเครื่องเท่านั้น

---

## 🛠️ โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

```text
├── app.py                          # FastAPI service หลัก (endpoint /analyze, /health)
├── launcher.py                     # ตัวรัน app.py แบบ system tray (สำหรับแพ็คเป็น .exe)
├── path_utils.py                   # Helper หา path โมเดล/config ทั้งตอนรันแบบ .py และ .exe
├── pdf_extraction.py                # ระบบสกัดข้อความจาก PDF + OCR fallback + ดึงสกิลจากกราฟิก (visual skill extraction)
├── llm_providers.py                 # ตัวเชื่อมต่อและจัดการโมเดล LLM หลายค่าย + extract_visual_skills (Gemini vision)
├── clean_skill_dictionary.py        # สคริปต์ทำความสะอาดพจนานุกรมทักษะ (2-tier filter)
├── rebuild_entity_ruler.py          # สคริปต์สร้าง spaCy EntityRuler จาก pattern ที่กรองแล้ว
├── compare_models.py                # สคริปต์เปรียบเทียบประสิทธิภาพโมเดล/provider
├── test_full_pipeline_v4.py         # Pipeline หลัก: SBERT matching + skill extraction + LLM
├── local_manual_scripts/            # สคริปต์สำหรับรันมือ/debug เฉพาะกิจ (ไม่ใช่ส่วนของ service) ดูรายละเอียดด้านล่าง
├── modelname.py                     # กำหนดค่าตัวแปรและชื่อโมเดลที่ใช้งาน
├── cleaned_hard_final2.jsonl        # พจนานุกรม Hard Skills (Pattern Rules)
├── cleaned_soft.jsonl               # พจนานุกรม Soft Skills (Pattern Rules)
├── requirements.txt                 # รายการไลบรารี Dependencies ที่จำเป็น
├── .env.example                     # ไฟล์ตัวอย่างสำหรับการตั้งค่า API Key
└── README.md                        # เอกสารอธิบายโครงการ (ไฟล์นี้)
```

---

## 🚀 ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน (Getting Started)

> วิธีนี้สำหรับรันจากซอร์สโค้ดโดยตรง เหมาะสำหรับนักพัฒนาที่ต้องการแก้ไข/ต่อยอดโค้ด หรือรันแต่ละ script แยกกัน (เช่น fine-tune SBERT, rebuild skill dictionary) ถ้าต้องการแค่ใช้งาน API เฉยๆ ดูหัวข้อ [ดาวน์โหลดตัวติดตั้ง](#-ดาวน์โหลดตัวติดตั้ง-windows-installer) แทน

### 1. ติดตั้ง Dependencies

```bash
git clone https://github.com/Kira101111010110/ai-resume-jd-matcher.git
cd ai-resume-jd-matcher
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` จาก `.env.example` แล้วระบุ API Key ของ LLM ที่ต้องการใช้งาน (ใส่อย่างน้อย 1 ตัว):

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here
ANTHROPIC_API_KEY=your_api_key_here

# เปิด/ปิดการดึงสกิลจากกราฟิกในเรซูเม่ (default: true) — ต้องมี GEMINI_API_KEY เสมอ ไม่ว่าจะเลือก provider ไหน
VISUAL_SKILL_EXTRACTION=true
VISION_MODEL_NAME=gemini-3.6-flash
```

### 3. เตรียมชุดกฎของโมเดลสกัดสกิล (Build Entity Ruler)

```bash
python rebuild_entity_ruler.py
```

### 4. รันระบบหรือรันทดสอบ Pipeline

รันทดสอบ Full Pipeline (E2E):

```bash
python test_full_pipeline_v4.py
```

เปิดใช้งาน API service หลัก:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

จากนั้นเข้า `http://localhost:8000/docs` เพื่อทดสอบ API ผ่านหน้า Swagger UI

---

## 🖼️ สกัดสกิลจากกราฟิกในเรซูเม่ (Visual Skill Extraction)

เรซูเม่จำนวนมาก (โดยเฉพาะเทมเพลตจาก Canva) แสดงทักษะเป็น**กราฟิก**แทนข้อความล้วน เช่น skill bar, กราฟวงกลม/เปอร์เซ็นต์, ดาว/จุด rating หรือไอคอน-โลโก้เทคโนโลยี ซึ่ง `pdfplumber`/OCR ธรรมดาอ่านไม่ได้ ทำให้สกิลเหล่านี้หายไปจากการวิเคราะห์โดยไม่มี warning และผู้สมัครอาจโดนตัดคะแนน skill penalty อย่างไม่เป็นธรรม

**วิธีทำงาน** (ใน `pdf_extraction.extract_text_from_pdf_bytes`):
1. ตรวจแต่ละหน้า PDF ด้วย `pdfplumber` หาสัญญาณกราฟิกสกิล — ไอคอน/โลโก้ขนาดเล็ก (กันรูปโปรไฟล์ด้วยเกณฑ์พื้นที่), กลุ่มแถบสี่เหลี่ยมความสูงเท่ากันหลายแถบ (skill bar), หรือ curve จำนวนมาก (กราฟวงกลม/ดาว)
2. หน้าที่ตรวจพบ (ไม่เกิน 2 หน้า) จะถูก render เป็นภาพด้วย PyMuPDF แล้วส่งให้ **Gemini vision** (`llm_providers.extract_visual_skills`) อ่านชื่อสกิล — ใช้ Gemini เสมอไม่ว่าจะเลือก `model_provider` ใดใน `/analyze`
3. สกิลที่ได้จะถูกเทียบกับข้อความที่สกัดมาแล้ว (case-insensitive + กันจับคำย่อยอย่าง "C"/"R"/"Go") ตัดตัวที่ซ้ำออก แล้วต่อท้ายข้อความเป็นบรรทัด `Skills (from graphics): ...` — ผลคือ SBERT, spaCy skill extraction, `skill_overlap_ratio` และ storytelling เห็นสกิลเหล่านี้โดยอัตโนมัติ ไม่ต้องแก้ pipeline ส่วนอื่น

**Response fields ใหม่ใน `/analyze`:** `visual_skills` (list ของสกิลใหม่ที่ดึงได้จากกราฟิก) และ `visual_skills_used` (bool)

**ปลอดภัยต่อ `/analyze`:** ถ้าไม่มี `GEMINI_API_KEY`, Gemini error, timeout หรือ render ไม่ได้ ระบบจะข้ามขั้นนี้ไปใช้ข้อความเดิม แล้วแนบข้อความอธิบายไว้ใน `text_extraction_warning` แทนที่จะทำให้ request ล้มเหลว — เรซูเม่ที่ไม่มีกราฟิกสกิลเลยจะไม่ถูกเรียก Gemini เพิ่มและไม่ช้าลง

ปิดฟีเจอร์นี้ได้ด้วย env `VISUAL_SKILL_EXTRACTION=false` (ดูหัวข้อ [ตั้งค่า Environment Variables](#2-ตั้งค่า-environment-variables) ด้านบน)

**ทดสอบ:** `python local_manual_scripts/test_visual_skills.py path/to/resume.pdf` (รันจากไดเรกทอรีไหนก็ได้) พิมพ์หน้าที่ตรวจเจอ + เหตุผล, ตัวเลขดิบ (area ratio ของรูป/จำนวน rect-curve ต่อหน้า สำหรับจูน threshold), `visual_skills` และ 15 บรรทัดสุดท้ายของข้อความที่สกัดได้ — มี PDF ตัวอย่างไว้ทดสอบที่ `synthetic_resumes/visual/` (สร้างด้วย `local_manual_scripts/generate_visual_test_resumes.py`) ดูสคริปต์ manual/debug อื่นๆ ที่ `local_manual_scripts/` ทั้งหมดได้ในหัวข้อ [สคริปต์สำหรับรันมือ](#-สคริปต์สำหรับรันมือ-local_manual_scripts) ด้านล่าง

---

## 🗂️ สคริปต์สำหรับรันมือ (local_manual_scripts/)

โฟลเดอร์นี้รวมสคริปต์ที่เขียนขึ้นระหว่างพัฒนา/debug ฟีเจอร์ visual skill extraction และแก้ `skill_overlap_ratio`
**ไม่ใช่ส่วนหนึ่งของ service** (`app.py` ไม่ได้ import ไฟล์พวกนี้) เก็บไว้เผื่อต้อง debug/จูน threshold ซ้ำในอนาคต

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `test_visual_skills.py` | ดีบักการตรวจจับ/ดึงสกิลจากกราฟิกกับ PDF ไฟล์เดียว — `python local_manual_scripts/test_visual_skills.py path/to/resume.pdf` |
| `generate_visual_test_resumes.py` | สร้าง PDF ทดสอบกราฟิกสกิล 3 ไฟล์ (`synthetic_resumes/visual/A.pdf`, `B.pdf`, `C.pdf`) |
| `analyze_skill_noise.py` | วิเคราะห์ว่าคำใน `GENERIC_ROLE_WORDS` (ชื่อตำแหน่งงาน/คำ noise) กระทบ `skill_overlap_ratio` ของเรซูเม่ตัวอย่างชุดไหนบ้าง |
| `run_before_after_comparison.py` | ยิง `/analyze` จริงเทียบผลก่อน/หลังเปิด `VISUAL_SKILL_EXTRACTION` ผ่าน FastAPI `TestClient` |
| `before_after_comparison.json`, `skill_noise_analysis.json` | ผลลัพธ์ล่าสุดที่บันทึกไว้จาก 2 สคริปต์ด้านบน (ข้อมูล ไม่ใช่สคริปต์) |

**สำคัญ:** `analyze_skill_noise.py` และ `run_before_after_comparison.py` ต้องรันจาก **root ของ repo เท่านั้น** (เช่น `cd ai-resume-jd-matcher && python local_manual_scripts/analyze_skill_noise.py`) เพราะทั้งคู่ import `test_full_pipeline_v4.py` ซึ่งโหลดโมเดล SBERT ด้วย relative path ที่ผูกกับ working directory — เป็นพฤติกรรมเดิมของไฟล์นั้น ไม่เกี่ยวกับตำแหน่งของสคริปต์ในโฟลเดอร์นี้ ส่วน `test_visual_skills.py` และ `generate_visual_test_resumes.py` รันจากไดเรกทอรีไหนก็ได้ (resolve path เทียบกับตำแหน่งไฟล์เอง)

---

## 📊 ผลการประเมิน (Evaluation Summary)

| Metric | ก่อน Fine-tune | หลัง Fine-tune |
|---|---|---|
| Spearman correlation | 0.357 | **0.850** |
| Pearson correlation | 0.372 | **0.856** |

เปรียบเทียบ LLM provider จาก 432 combination (18 resumes × 8 JDs × 3 providers): **Gemini 100%** label accuracy, gpt-4o-mini ~72.1%, Claude ~70.9%

---

## 👥 ทีมพัฒนา

โครงงานวิศวกรรมคอมพิวเตอร์ Rajamangala University of Technology Lanna
