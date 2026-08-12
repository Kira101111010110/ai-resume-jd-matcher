# 📄 Intelligent Resume Screening & JD Matching System
> ระบบคัดกรองและประเมินความเหมาะสมของเรซูเม่กับตำแหน่งงาน (Job Description) อัตโนมัติด้วยเทคนิค NLP, Pattern-based Skill Extraction และโมเดลภาษาขนาดใหญ่ (LLM)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![spaCy](https://img.shields.io/badge/spaCy-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![OpenAI / LLM](https://img.shields.io/badge/LLM-Providers-412991?style=for-the-badge&logo=openai&logoColor=white)

---

## 📌 ภาพรวมโครงการ (Project Overview)
โครงการนี้พัฒนาขึ้นเพื่อเพิ่มประสิทธิภาพในการคัดกรองผู้สมัครงานของฝ่ายบุคคล (HR) โดยระบบสามารถดึงข้อความจากไฟล์เรซูเม่ PDF, สกัดทักษะทั้ง Hard Skills และ Soft Skills อย่างแม่นยำด้วย Rule-based / Entity Ruler และนำมาจับคู่เปรียบเทียบความเข้ากันได้กับ Job Description (JD) ผ่านโมเดล AI เพื่อจัดอันดับและวิเคราะห์จุดเด่น-จุดด้อยของผู้สมัคร

---

## ✨ คุณสมบัติเด่น (Core Features)
* **Automated PDF Text Extraction:** แปลงและสกัดข้อความจากเรซูเม่ไฟล์ PDF รองรับหลากหลายเลย์เอาต์ (`pdf_extraction.py`)
* **Accurate Skill Extraction:** สกัดทักษะเฉพาะทาง (Hard Skills & Soft Skills) ด้วยพจนานุกรมคำศัพท์และ spaCy Entity Ruler (`rebuild_entity_ruler.py`, `cleaned_hard_final2.jsonl`, `cleaned_soft.jsonl`)
* **Multi-LLM Provider Integration:** รองรับการประมวลผลและการจัดอันดับความเหมาะสมผ่านโมเดลภาษาขนาดใหญ่หลากหลายค่าย (`llm_providers.py`)
* **Model Comparison & Evaluation:** มีระบบทดสอบและเปรียบเทียบประสิทธิภาพของแต่ละ Pipeline/Model (`compare_models.py`, `test_full_pipeline_v4.py`)
* **Web/API Application:** พร้อมเชื่อมต่อใช้งานจริงผ่าน Backend API (`app.py`)

---

## 🛠️ โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

```text
├── app.py                          # สคริปต์หลักของแอปพลิเคชัน / API Server
├── pdf_extraction.py               # ระบบสกัดข้อความจากเอกสาร PDF
├── llm_providers.py                # ตัวเชื่อมต่อและจัดการโมเดล LLM
├── clean_skill_dictionary.py       # สคริปต์ทำความสะอาดและจัดกลุ่มคำศัพท์ทักษะ
├── rebuild_entity_ruler.py         # สคริปต์สร้าง Rules สำหรับโมเดล Entity Extraction
├── compare_models.py               # สคริปต์เปรียบเทียบประสิทธิภาพโมเดล
├── test_full_pipeline_v4.py        # สคริปต์ทดสอบกระบวนการทำงานตั้งแต่ต้นจนจบ (E2E Test)
├── modelname.py                    # กำหนดค่าตัวแปรและชื่อโมเดลที่ใช้งาน
├── cleaned_hard_final2.jsonl       # พจนานุกรม Hard Skills (Pattern Rules)
├── cleaned_soft.jsonl              # พจนานุกรม Soft Skills (Pattern Rules)
├── requirements.txt                # รายการไลบรารี Dependencies ที่จำเป็น
├── .env.example                    # ไฟล์ตัวอย่างสำหรับการตั้งค่า API Key
└── README.md                       # เอกสารอธิบายโครงการ
```

🚀 ขั้นตอนการติดตั้งและเริ่มต้นใช้งาน (Getting Started)
1. ติดตั้ง Dependencies```
Bash
git clone [https://github.com/Kira101111010110/intelligent-resume-screening-system.git](https://github.com/Kira101111010110/intelligent-resume-screening-system.git)
cd intelligent-resume-screening-system
pip install -r requirements.txt```
2. ตั้งค่า Environment Variables
สร้างไฟล์ .env จาก .env.example แล้วระบุ API Key ของ LLM ที่ต้องการใช้งาน:
```
Bash
cp .env.example .env
ข้อมูลโค้ด
OPENAI_API_KEY=your_api_key_here
```

3. เตรียมชุดกฎของโมเดลสกัดสกิล (Build Entity Ruler)```
Bash
python rebuild_entity_ruler.py```
4. รันระบบหรือรันทดสอบ Pipeline
รันทดสอบ Full Pipeline:
```

Bash
python test_full_pipeline_v4.py
```
เปิดใช้งานแอปพลิเคชันหลัก:
```
Bash
python app.py
