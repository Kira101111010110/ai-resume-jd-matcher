"""
เปรียบเทียบผลลัพธ์การวิเคราะห์ storytelling ข้ามหลาย provider/รุ่น ด้วย resume+job เดียวกัน
ใช้ resume/job เดิมทุกครั้ง เพื่อให้เห็นว่าแต่ละเจ้า "ตอบต่างกันแค่ไหน" กับ input เดียวกัน

วิธีใช้:
    python compare_models.py

ถ้า provider ไหนยังไม่ได้ตั้ง API key ไว้ (ใน environment variable) จะข้ามไปเฉยๆ
พร้อมบอกว่าต้องตั้ง env var ตัวไหนเพิ่ม ไม่ทำให้ script ทั้งชุดพัง
"""

import os
from llm_providers import analyze_storytelling

test_resume = """
Experienced backend developer with 5 years building scalable systems.
Led a team of 4 engineers to redesign the payment processing pipeline,
reducing transaction failures by 35% and improving response time from 
800ms to 200ms. Skilled in Python, AWS, PostgreSQL, and team leadership.
Strong communication skills, worked closely with product managers to 
define requirements.
"""

test_job = """
Looking for a Senior Backend Engineer with strong Python skills.
Must have experience with cloud infrastructure (AWS preferred) and 
database systems. Leadership experience is a plus. Good communication 
skills required to work with cross-functional teams.
"""

# แต่ละรายการคือ (provider, model_name, ชื่อ env var ที่ต้องมี key)
CANDIDATES = [
    ("gemini", "gemini-3-flash-preview", "GEMINI_API_KEY"),
    ("openai", "gpt-4o-mini", "OPENAI_API_KEY"),
    ("claude", "claude-sonnet-4-5", "ANTHROPIC_API_KEY"),
]


def main():
    results = []

    for provider, model_name, env_key in CANDIDATES:
        if not os.environ.get(env_key):
            print(f"⏭️  ข้าม {provider} ({model_name}) — ยังไม่ได้ตั้งค่า {env_key}")
            continue

        print(f"\n{'=' * 60}")
        print(f"กำลังทดสอบ: {provider} / {model_name}")
        print("=" * 60)

        try:
            result = analyze_storytelling(
                test_resume, test_job, provider=provider, model_name=model_name
            )
            results.append(result)
            print(f"score={result.get('storytelling_score')}  "
                  f"confidence={result.get('confidence')}  "
                  f"latency={result.get('latency_seconds')}s")
            print(f"reason: {result.get('ai_reason')}")
        except Exception as e:
            print(f"❌ error: {e}")

    if not results:
        print("\nยังไม่มี provider ไหนพร้อมทดสอบเลย (มีแค่ Gemini ตอนนี้)")
        return

    print(f"\n{'=' * 60}")
    print("สรุปเปรียบเทียบ")
    print("=" * 60)
    print(f"{'Provider':<10} {'Model':<25} {'Score':<8} {'Confidence':<12} {'Latency(s)':<10}")
    for r in results:
        print(f"{r.get('provider', ''):<10} "
              f"{'':<25} "
              f"{str(r.get('storytelling_score')):<8} "
              f"{str(r.get('confidence')):<12} "
              f"{str(r.get('latency_seconds')):<10}")


if __name__ == "__main__":
    main()
