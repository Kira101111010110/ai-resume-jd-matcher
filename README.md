# 📄 Intelligent Resume Screening & JD Matching System

> ระบบคัดกรองและประเมินความเหมาะสมของเรซูเม่กับตำแหน่งงาน (Job Description) อัตโนมัติด้วยเทคนิค NLP, Pattern-based Skill Extraction และโมเดลภาษาขนาดใหญ่ (LLM)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![spaCy](https://img.shields.io/badge/spaCy-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![OpenAI / LLM](https://img.shields.io/badge/LLM-Providers-412991?style=for-the-badge&logo=openai&logoColor=white)

---

## 📌 ภาพรวมโครงการ (Project Overview)

โครงการนี้พัฒนาขึ้นเพื่อเพิ่มประสิทธิภาพในการคัดกรองผู้สมัครงานของฝ่ายบุคคล (HR) โดยระบบสามารถดึงข้อความจากไฟล์เรซูเม่ PDF สกัดทักษะทั้ง Hard Skills และ Soft Skills ด้วย spaCy Entity Ruler วัดความเข้ากันได้กับ Job Description (JD) ด้วย Fine-tuned SBERT และให้ LLM วิเคราะห์การเล่าเรื่อง (Storytelling) เพื่อจัดอันดับและสรุปจุดเด่น-จุดด้อยของผู้สมัคร

---

## ✨ คุณสมบัติเด่น (Core Features)

* **Automated PDF Text Extraction** — สกัดข้อความจากเรซูเม่ PDF รองรับหลายเลย์เอาต์ พร้อม OCR fallback (ไทย/อังกฤษ) สำหรับไฟล์ที่มีปัญหาฟอนต์ (`pdf_extraction.py`)
* **Visual Skill Extraction** — ตรวจจับกราฟิกแสดงทักษะ (skill bar, กราฟวงกลม %, ดาว/จุด rating, โลโก้เทคโนโลยี) แล้วให้ Gemini vision อ่านชื่อสกิล — ดู[รายละเอียดด้านล่าง](#️-สกัดสกิลจากกราฟิกในเรซูเม่-visual-skill-extraction)
* **Fine-tuned SBERT Matching** — วัดความเข้ากันได้ระหว่าง Resume กับ JD ด้วย Semantic Similarity (fine-tune จาก `all-mpnet-base-v2`, Spearman correlation 0.357 → 0.850)
* **Accurate Skill Extraction** — สกัด Hard/Soft Skills ด้วยพจนานุกรมที่ทำความสะอาดแล้ว (`skill_dictionary/`) — `skill_overlap_ratio` กรองคำทั่วไป (ชื่อตำแหน่งงาน, คำ noise) ออกทั้ง 2 ฝั่งก่อนเทียบ
* **Multi-LLM Provider** — วิเคราะห์ Storytelling ผ่าน Gemini / OpenAI / Claude แบบสลับได้ (`llm_providers.py`)
* **FastAPI Service** — `/analyze` รองรับทั้ง `resume_text` และ `resume_url` (`app.py`) deploy ด้วย Docker / Hugging Face Spaces
* **โปรแกรม Windows (.exe)** — หน้าเว็บในเครื่องสำหรับคนที่ไม่อยากตั้งค่า Python เอง (`exe/`)

---

## 🎯 เลือกวิธีใช้งาน

| | 💾 โปรแกรม Windows (Installer) | 🧑‍💻 รันจากซอร์สโค้ด / Docker |
|---|---|---|
| เหมาะกับ | วิเคราะห์เรซูเม่ทันทีผ่านหน้าเว็บในเครื่อง ไม่ต้องตั้งค่าอะไรเอง (เช่น อาจารย์ใช้ในรายวิชา) | แก้โค้ด, ต่อยอด, deploy API หรือรัน pipeline แยกส่วน |
| ต้องติดตั้ง Python เอง | ❌ ไม่ต้อง | ✅ Python 3.10+ (หรือใช้ Docker) |
| ดูวิธีใช้ | [ดาวน์โหลดโปรแกรม](#-ดาวน์โหลดโปรแกรม-windows-installer) | [ขั้นตอนการติดตั้ง](#-ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน-getting-started) |

---

## 🛠️ โครงสร้างโปรเจกต์ (Project Structure)

```text
ai-resume-jd-matcher/
├── app.py                       # FastAPI service หลัก (/analyze, /health)
├── test_full_pipeline_v4.py     # Pipeline หลัก: SBERT matching + skill extraction + LLM storytelling
├── pdf_extraction.py            # สกัดข้อความจาก PDF + OCR fallback + ดึงสกิลจากกราฟิก
├── llm_providers.py             # เชื่อมต่อ LLM หลายค่าย + extract_visual_skills (Gemini vision)
├── requirements.txt             # dependency ของ API
├── Dockerfile                   # image สำหรับ Hugging Face Spaces / Railway (ดาวน์โหลดโมเดลจาก Releases ให้เอง)
├── env.example                  # ตัวอย่างไฟล์ .env (API key)
│
├── exe/                         # 💾 โปรแกรม Windows (.exe + ตัวติดตั้ง) — ดู exe/README.md
│   ├── desktop/                 #    หน้าเว็บในเครื่อง, หน้าตั้งค่า, system tray, build script, Inno Setup
│   └── *.py                     #    โค้ด AI เวอร์ชันที่ exe ใช้
│
├── skill_dictionary/            # 🧹 พจนานุกรมทักษะ + สคริปต์สร้าง skill-extractor-model
│   ├── clean_skill_dictionary.py
│   ├── rebuild_entity_ruler.py
│   └── cleaned_*.jsonl          #    pattern ของ Hard / Soft Skills
│
├── research/                    # 📊 สคริปต์ทดลอง/เปรียบเทียบโมเดล (ไม่ใช่ส่วนของ API)
│   ├── run_comparison.py        #    เรซูเม่ทุกใบ × JD ทุกตำแหน่ง × ทุก provider → CSV
│   ├── run_comparison_openai_retest.py, merge_openai_retest.py   # รัน OpenAI รุ่นใหม่ซ้ำแล้วรวมผล
│   ├── compare_models.py        #    เทียบผล storytelling ข้าม provider ด้วย input เดียวกัน
│   ├── generate_synthetic_resumes.py  # สร้างเรซูเม่จำลอง 18 ใบใน synthetic_resumes/
│   └── modelname.py             #    เช็ครายชื่อโมเดลที่ API key ใช้ได้จริง
│
├── local_manual_scripts/        # 🔧 สคริปต์ debug ฟีเจอร์ visual skill extraction
│
└── synthetic_resumes/           # 🧪 ข้อมูลทดสอบ
    ├── pdf/, txt/               #    เรซูเม่จำลอง 18 ใบ (PDF + ข้อความ)
    ├── visual/                  #    PDF ที่มีสกิลเป็นกราฟิก (A, B, C)
    ├── job_descriptions.json    #    JD 8 ตำแหน่ง
    └── manifest.csv             #    รายละเอียดเรซูเม่แต่ละใบ
```

โมเดลที่ fine-tune แล้ว (`resume-jd-matcher-model/`, `skill-extractor-model/`) ใหญ่เกิน git — เก็บไว้ที่ [Releases `v1.0-models`](../../releases/tag/v1.0-models)

---

## 💾 ดาวน์โหลดโปรแกรม (Windows Installer)

**[⬇️ ดาวน์โหลดตัวติดตั้ง (Releases ล่าสุด)](../../releases/latest)**

- ติดตั้งได้โดย**ไม่ต้องใช้สิทธิ์ admin** และไม่ต้องลง Python / Tesseract เพิ่ม (รวม Python, SBERT, spaCy, torch แบบ CPU และ Tesseract OCR ภาษาไทยไว้ในตัวแล้ว)
- Windows อาจเตือน **"Windows protected your PC"** ตอนเปิดตัวติดตั้ง (exe ยังไม่ได้ sign) → กด **More info → Run anyway**
- เปิดครั้งแรกจะมีหน้าตั้งค่าให้กรอก API Key (Gemini / OpenAI / Claude อย่างน้อย 1 ตัว) — key เก็บไว้ในเครื่องเท่านั้น
- มีคู่มือภาษาไทยในตัวโปรแกรม และปุ่ม "ลองด้วยเรซูเม่ตัวอย่าง"

วิธี build โปรแกรมเอง ดูที่ [`exe/desktop/README.md`](exe/desktop/README.md)

---

## 🚀 ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน (Getting Started)

### 1. ติดตั้ง Dependencies

```bash
git clone https://github.com/Kira101111010110/ai-resume-jd-matcher.git
cd ai-resume-jd-matcher
pip install -r requirements.txt
```

### 2. ดาวน์โหลดโมเดล

ดาวน์โหลด `resume-jd-matcher-model.zip` และ `skill-extractor-model.zip` จาก [Releases `v1.0-models`](../../releases/tag/v1.0-models) แล้วแตกไฟล์ไว้ที่ root ของ repo:

```text
ai-resume-jd-matcher/
├── resume-jd-matcher-model/
└── skill-extractor-model/
```

### 3. ตั้งค่า Environment Variables

```bash
cp env.example .env
```

```env
GEMINI_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here
ANTHROPIC_API_KEY=your_api_key_here

# เปิด/ปิดการดึงสกิลจากกราฟิกในเรซูเม่ (default: true) — ต้องมี GEMINI_API_KEY เสมอ ไม่ว่าจะเลือก provider ไหน
VISUAL_SKILL_EXTRACTION=true
VISION_MODEL_NAME=gemini-3.6-flash
```

### 4. รัน API

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

จากนั้นเข้า `http://localhost:8000/docs` เพื่อทดสอบผ่านหน้า Swagger UI

ทดสอบ pipeline เต็ม (E2E) โดยไม่ผ่าน API: `python test_full_pipeline_v4.py`

### หรือรันด้วย Docker

```bash
docker build -t resume-ai .
docker run -p 7860:7860 --env-file .env resume-ai
```

Dockerfile ดาวน์โหลดโมเดลจาก Releases ให้เอง ไม่ต้องทำขั้นที่ 2

> **หมายเหตุ:** คำสั่งทั้งหมดในหัวข้อนี้ และสคริปต์ใน `research/`, `local_manual_scripts/` ให้รันจาก **root ของ repo** เพราะ `test_full_pipeline_v4.py` โหลดโมเดลด้วย path สัมพัทธ์

---

## 🧹 สร้าง skill-extractor-model ใหม่ (Skill Dictionary)

ใช้เมื่อแก้พจนานุกรมทักษะ (เพิ่ม/ลบสกิล หรือกรองคำ noise) — EntityRuler เป็น rule-based ไม่ต้องเทรนบน GPU รันไม่กี่วินาที

```bash
# 1. (ถ้ามีรายการสกิลดิบใหม่) ทำความสะอาดพจนานุกรม
python skill_dictionary/clean_skill_dictionary.py --input raw_skills.txt --output cleaned_patterns.jsonl

# 2. สร้างโมเดลจาก pattern ที่กรองแล้ว (ต้องมี en_core_web_lg: python -m spacy download en_core_web_lg)
python skill_dictionary/rebuild_entity_ruler.py \
    --hard-patterns skill_dictionary/cleaned_hard_final2.jsonl \
    --soft-patterns skill_dictionary/cleaned_soft.jsonl \
    --output ./skill-extractor-model \
    --base-model en_core_web_lg
```

แล้ว restart uvicorn เพื่อให้ API โหลดโมเดลใหม่

---

## 🖼️ สกัดสกิลจากกราฟิกในเรซูเม่ (Visual Skill Extraction)

เรซูเม่จำนวนมาก (โดยเฉพาะเทมเพลตจาก Canva) แสดงทักษะเป็น**กราฟิก**แทนข้อความ เช่น skill bar, กราฟวงกลม/เปอร์เซ็นต์, ดาว/จุด rating หรือโลโก้เทคโนโลยี ซึ่ง `pdfplumber`/OCR ธรรมดาอ่านไม่ได้ ทำให้สกิลหายไปจากการวิเคราะห์และผู้สมัครอาจโดนตัดคะแนนอย่างไม่เป็นธรรม

**วิธีทำงาน** (ใน `pdf_extraction.extract_text_from_pdf_bytes`):
1. ตรวจแต่ละหน้า PDF ด้วย `pdfplumber` หาสัญญาณกราฟิกสกิล — ไอคอน/โลโก้ขนาดเล็ก (กันรูปโปรไฟล์ด้วยเกณฑ์พื้นที่), กลุ่มแถบสี่เหลี่ยมความสูงเท่ากัน (skill bar) หรือ curve จำนวนมาก (กราฟวงกลม/ดาว)
2. หน้าที่ตรวจพบ (ไม่เกิน 2 หน้า) ถูก render เป็นภาพด้วย PyMuPDF แล้วส่งให้ **Gemini vision** (`llm_providers.extract_visual_skills`) อ่านชื่อสกิล — ใช้ Gemini เสมอไม่ว่าจะเลือก `model_provider` ใด
3. ตัดสกิลที่ซ้ำกับข้อความเดิมออก (case-insensitive + กันจับคำย่อยอย่าง "C"/"R"/"Go") แล้วต่อท้ายเป็นบรรทัด `Skills (from graphics): ...` — SBERT, skill extraction, `skill_overlap_ratio` และ storytelling จึงเห็นสกิลเหล่านี้อัตโนมัติ

**Response fields ใน `/analyze`:** `visual_skills` (สกิลที่ดึงได้จากกราฟิก) และ `visual_skills_used` (bool)

**ไม่ทำให้ request ล้ม:** ถ้าไม่มี `GEMINI_API_KEY`, Gemini error/timeout หรือ render ไม่ได้ ระบบข้ามขั้นนี้แล้วแนบคำอธิบายไว้ใน `text_extraction_warning` — เรซูเม่ที่ไม่มีกราฟิกสกิลจะไม่เรียก Gemini เพิ่ม

ปิดฟีเจอร์ได้ด้วย `VISUAL_SKILL_EXTRACTION=false`

### สคริปต์ debug (`local_manual_scripts/`)

ไม่ใช่ส่วนของ service (`app.py` ไม่ได้ import) เก็บไว้สำหรับจูน threshold ภายหลัง

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `test_visual_skills.py` | ดีบักการตรวจจับ/ดึงสกิลจากกราฟิกกับ PDF ไฟล์เดียว — `python local_manual_scripts/test_visual_skills.py synthetic_resumes/visual/C.pdf` |
| `generate_visual_test_resumes.py` | สร้าง PDF ทดสอบ `synthetic_resumes/visual/A.pdf`, `B.pdf`, `C.pdf` |
| `analyze_skill_noise.py` | วิเคราะห์ว่าคำใน `GENERIC_ROLE_WORDS` กระทบ `skill_overlap_ratio` ของเรซูเม่ชุดไหนบ้าง |
| `run_before_after_comparison.py` | ยิง `/analyze` เทียบผลก่อน/หลังเปิด `VISUAL_SKILL_EXTRACTION` |
| `*.json` | ผลลัพธ์ล่าสุดที่บันทึกไว้จาก 2 สคริปต์ด้านบน |

---

## 📊 ผลการประเมิน (Evaluation Summary)

| Metric | ก่อน Fine-tune | หลัง Fine-tune |
|---|---|---|
| Spearman correlation | 0.357 | **0.850** |
| Pearson correlation | 0.372 | **0.856** |

เปรียบเทียบ LLM provider จาก 432 combination (18 resumes × 8 JDs × 3 providers): **Gemini 100%** label accuracy, gpt-4o-mini ~72.1%, Claude ~70.9% — รันซ้ำได้ด้วย `python research/run_comparison.py`

---

## 👥 ทีมพัฒนา

โครงงานวิศวกรรมคอมพิวเตอร์ Rajamangala University of Technology Lanna
