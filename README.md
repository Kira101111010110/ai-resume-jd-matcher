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
* **Fine-tuned SBERT Matching** — วัดความเข้ากันได้ระหว่าง Resume กับ JD ด้วย Semantic Similarity (fine-tune จาก `all-mpnet-base-v2`, Spearman correlation 0.357 → 0.850)
* **Accurate Skill Extraction** — สกัดทักษะเฉพาะทาง (Hard Skills & Soft Skills) ด้วยพจนานุกรมคำศัพท์ที่ทำความสะอาดแล้วและ spaCy Entity Ruler (`rebuild_entity_ruler.py`, `cleaned_hard_final2.jsonl`, `cleaned_soft.jsonl`)
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
├── pdf_extraction.py                # ระบบสกัดข้อความจาก PDF + OCR fallback
├── llm_providers.py                 # ตัวเชื่อมต่อและจัดการโมเดล LLM หลายค่าย
├── clean_skill_dictionary.py        # สคริปต์ทำความสะอาดพจนานุกรมทักษะ (2-tier filter)
├── rebuild_entity_ruler.py          # สคริปต์สร้าง spaCy EntityRuler จาก pattern ที่กรองแล้ว
├── compare_models.py                # สคริปต์เปรียบเทียบประสิทธิภาพโมเดล/provider
├── test_full_pipeline_v4.py         # Pipeline หลัก: SBERT matching + skill extraction + LLM
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

## 📊 ผลการประเมิน (Evaluation Summary)

| Metric | ก่อน Fine-tune | หลัง Fine-tune |
|---|---|---|
| Spearman correlation | 0.357 | **0.850** |
| Pearson correlation | 0.372 | **0.856** |

เปรียบเทียบ LLM provider จาก 432 combination (18 resumes × 8 JDs × 3 providers): **Gemini 100%** label accuracy, gpt-4o-mini ~72.1%, Claude ~70.9%

---

## 👥 ทีมพัฒนา

โครงงานวิศวกรรมคอมพิวเตอร์ Rajamangala University of Technology Lanna
