import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai

# โหลดค่าจากไฟล์ .env (เพื่อให้ดึง GEMINI_API_KEY มาใช้ได้)
load_dotenv()

# ดึง API Key
api_key = os.environ.get("GEMINI_API_KEY", "")

if not api_key:
    print("⚠️  ไม่พบ GEMINI_API_KEY โปรดเช็คไฟล์ .env หรือ Environment Variable")
else:
    genai.configure(api_key=api_key)

    print("--- รายชื่อโมเดลที่ใช้สร้างข้อความได้ (generateContent) ---")
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                print(m.name.replace("models/", ""))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงรายชื่อโมเดล: {e}")