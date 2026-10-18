"""
สคริปต์เช็ครายชื่อโมเดลที่ใช้งานได้จริง (ผ่าน API key ที่มี) จากทั้ง 3 ค่าย
พร้อมคำแนะนำ Top 3 ของแต่ละค่าย สำหรับงาน Storytelling Scoring (ต้องการ JSON output
ที่แม่นยำ + เข้าใจภาษาไทย เป็นหลัก ไม่ใช่งาน coding agent ยาวๆ)

หมายเหตุ: รายชื่อโมเดลของ Gemini/OpenAI/Claude ดึงจาก API จริงตอนรัน (จะอัปเดตเองเสมอ)
ส่วน "คำแนะนำ Top 3" เป็นความเห็น ณ ช่วงเวลาที่เขียนสคริปต์นี้ (ส.ค. 2026) — ค่าย AI
เปลี่ยนชื่อ/ออกรุ่นใหม่บ่อยมาก ควรเช็คของจริงจาก list ด้านบนก่อนใช้เสมอ
"""

import os
from dotenv import load_dotenv

load_dotenv()


def check_gemini():
    print("\n=== Gemini (Google) — โมเดลที่ใช้ generateContent ได้ ===")
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("⚠️  ไม่พบ GEMINI_API_KEY โปรดเช็คไฟล์ .env")
        return

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                print(" -", m.name.replace("models/", ""))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงรายชื่อโมเดล Gemini: {e}")


def check_openai():
    print("\n=== OpenAI — โมเดลที่ Account นี้เรียกใช้ได้ ===")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("⚠️  ไม่พบ OPENAI_API_KEY โปรดเช็คไฟล์ .env")
        return

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        # เอาเฉพาะรุ่นตระกูล gpt/o ที่น่าจะใช้แชท/reasoning ได้ ไม่เอา whisper/embedding/tts ให้รกตา
        names = sorted(
            m.id for m in models.data
            if m.id.startswith("gpt-") or m.id.startswith("o")
        )
        for name in names:
            print(" -", name)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงรายชื่อโมเดล OpenAI: {e}")


def check_claude():
    print("\n=== Anthropic Claude — โมเดลที่เรียกผ่าน API ได้ ===")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("⚠️  ไม่พบ ANTHROPIC_API_KEY โปรดเช็คไฟล์ .env")
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        for m in client.models.list():
            print(" -", m.id)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงรายชื่อโมเดล Claude: {e}")


def print_recommendations():
    print("\n" + "=" * 60)
    print("คำแนะนำ Top 3 ของแต่ละค่าย (สำหรับงาน storytelling scoring")
    print("ที่ต้องพึ่งความแม่นยำ + ภาษาไทย + คุมงบ ไม่ใช่งาน coding agent)")
    print("=" * 60)

    print("\n[Gemini]")
    print(" 1. gemini-3.6-flash        — ตัวที่แนะนำเป็นค่า default: คุณภาพดี ราคาถูกกว่ารุ่นก่อน")
    print(" 2. gemini-3.1-pro-preview  — ถ้าต้องการ reasoning ลึกกว่า Flash (ราคาสูงกว่ามาก)")
    print(" 3. gemini-3.5-flash-lite / gemini-3.1-flash-lite — ประหยัดสุด เผื่อ rate limit ตึง")

    print("\n[OpenAI]")
    print(" 1. gpt-5.6-terra — จุดสมดุลราคา/คุณภาพ เหมาะเป็น default")
    print(" 2. gpt-5.6-sol   — เรือธง แม่นสุด แต่แพงกว่า terra หลายเท่า")
    print(" 3. gpt-5.6-luna  — ถูกสุด เร็วสุด เผื่อ test จำนวนมาก/งบจำกัด")

    print("\n[Claude]")
    print(" 1. claude-sonnet-5 — จุดสมดุลราคา/คุณภาพ เหมาะเป็น default (ใช้ในไฟล์ตอนนี้)")
    print(" 2. claude-haiku-4-5-20251001 — เร็ว/ถูก เผื่อ batch test เยอะๆ")
    print(" 3. claude-opus-4-8 — คุณภาพสูงสุดของสาย Opus ถ้างบไม่ใช่ปัญหา")

    print("\n⚠️  ชื่อโมเดลพวกนี้เปลี่ยน/ปลดระวางบ่อยมาก (โดยเฉพาะ Gemini) —")
    print("   ให้ยึดรายชื่อที่ดึงจาก API จริงด้านบนเป็นหลักเสมอ ก่อนแก้ model_name ในโค้ดจริง")


if __name__ == "__main__":
    check_gemini()
    check_openai()
    check_claude()
    print_recommendations()
