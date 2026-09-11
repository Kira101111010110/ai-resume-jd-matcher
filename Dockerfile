FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-tha \
    build-essential \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-dotenv
RUN python -m spacy download en_core_web_lg

# ดาวน์โหลดโมเดลที่เก็บไว้ใน GitHub Releases (v1.0-models)
# หมายเหตุ: ต้องใช้ unzip -o -q (overwrite แบบไม่ถาม + เงียบ) ไม่งั้น build จะค้าง
# เพราะไฟล์ในตัว zip มีชื่อชนกันแล้ว unzip จะถามยืนยันแบบ interactive
RUN mkdir -p resume-jd-matcher-model \
    && curl -L -o resume-jd-matcher-model.zip \
      https://github.com/Kira101111010110/ai-resume-jd-matcher/releases/download/v1.0-models/resume-jd-matcher-model.zip \
    && unzip -o -q resume-jd-matcher-model.zip -d resume-jd-matcher-model \
    && rm resume-jd-matcher-model.zip \
    && mkdir -p skill-extractor-model \
    && curl -L -o skill-extractor-model.zip \
      https://github.com/Kira101111010110/ai-resume-jd-matcher/releases/download/v1.0-models/skill-extractor-model.zip \
    && unzip -o -q skill-extractor-model.zip -d skill-extractor-model \
    && rm skill-extractor-model.zip

COPY . .

# เผื่อเอกสาร/แพลตฟอร์มที่อ่าน EXPOSE แบบ static (HF อ่านค่านี้)
EXPOSE 7860

# HF Spaces ไม่ตั้งตัวแปร PORT มาให้ -> fallback เป็น 7860
# Railway (และ platform อื่นที่ inject $PORT) จะ override อัตโนมัติ
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
