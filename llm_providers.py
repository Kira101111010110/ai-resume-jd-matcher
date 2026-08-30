"""
Layer กลางสำหรับเรียก LLM หลายเจ้า ให้ full_analysis_pipeline เลือกใช้ได้
รองรับ: Gemini (ใช้งานได้จริงตอนนี้), OpenAI, Anthropic Claude (โครงพร้อม รอ API key)

การเพิ่มเจ้าใหม่ในอนาคต: เขียนฟังก์ชันใหม่ตาม pattern เดียวกับที่มีอยู่
แล้วเพิ่มเข้า PROVIDERS dict ด้านล่างสุดของไฟล์
"""

import os
import json
import time
import re
from dotenv import load_dotenv
 
load_dotenv()  # อ่านค่าจากไฟล์ .env เข้ามาเป็น environment variable ให้อัตโนมัติ

STORYTELLING_PROMPT_TEMPLATE = """วิเคราะห์ resume ต่อไปนี้ในแง่การเล่าเรื่องแบบมืออาชีพ (Problem → Action → Result)
และประเมินความเหมาะสมกับตำแหน่งงานที่สมัคร (ถ้ามีระบุ Job Description ด้านล่าง)

Resume:
{resume_text}

{job_line}

ตอบเป็น JSON เท่านั้น ในรูปแบบนี้:
{{
  "storytelling_score": "High" หรือ "Medium" หรือ "Low",
  "ai_reason": "สรุปจุดเด่น/จุดด้อยเป็นภาษาไทย 2-3 ประโยค",
  "has_quantified_results": true หรือ false,
  "strengths": ["จุดแข็ง 1", "จุดแข็ง 2"],
  "weaknesses": ["จุดที่ควรปรับปรุง 1"],
  "specific_strengths": "ถ้ามี Job Description ให้ประเมินว่าผู้สมัครเหมาะกับตำแหน่งนี้แค่ไหน โดยอ้างอิงจุดที่ตรงกันจริงระหว่าง resume กับ JD (ทักษะ/ประสบการณ์/ผลงาน) เป็นภาษาไทย 2-3 ประโยค แต่ถ้าไม่มี Job Description หรือ resume ไม่เกี่ยวข้องกับ JD เลย ให้บอกแทนว่าผู้สมัครมีจุดเด่นพิเศษอะไรที่น่าสนใจโดยไม่อิงกับตำแหน่งนี้ เช่น ทักษะหายาก ผลงานโดดเด่น หรือ certification พิเศษ",
  "confidence": ตัวเลข 0.0 ถึง 1.0 แสดงความมั่นใจของคุณเองในการวิเคราะห์นี้
}}"""


def _build_prompt(resume_text, job_text):
    job_line = f"Job Description ที่สมัคร: {job_text}" if job_text else ""
    return STORYTELLING_PROMPT_TEMPLATE.format(resume_text=resume_text, job_line=job_line)


def _strip_markdown_fence(text: str) -> str:
    """ลอก ```json ... ``` หรือ ``` ... ``` ที่บางเจ้า (โดยเฉพาะ Claude) ชอบห่อ JSON ไว้
    ก่อนส่งเข้า json.loads() เพราะไม่งั้นจะ parse fail ทั้งที่เนื้อหาข้างในถูกต้อง"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _parse_json_response(raw_text):
    cleaned = _strip_markdown_fence(raw_text)
    try:
        result = json.loads(cleaned)
        result.setdefault("confidence", 0.5)
        result.setdefault("specific_strengths", None)
        result["json_valid"] = True
        return result
    except json.JSONDecodeError:
        return {
            "storytelling_score": None,
            "ai_reason": None,
            "specific_strengths": None,
            "confidence": 0.0,
            "json_valid": False,
            "raw_response": raw_text
        }


# ============================================
# Gemini (ใช้งานได้จริง มี API key แล้ว)
# ============================================
def analyze_with_gemini(resume_text, job_text, model_name="gemini-3.6-flash"):
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel(model_name)
    prompt = _build_prompt(resume_text, job_text)

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json"
        )
    )
    return _parse_json_response(response.text)


# ============================================
# OpenAI (โครงพร้อม รอ API key มาทดสอบจริง)
# ============================================
def analyze_with_openai(resume_text, job_text, model_name="gpt-5.6-luna"):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า OPENAI_API_KEY — ต้องมี key ก่อนถึงจะเรียกเจ้านี้ได้")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(resume_text, job_text)

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return _parse_json_response(response.choices[0].message.content)


# ============================================
# Anthropic Claude (โครงพร้อม รอ API key มาทดสอบจริง)
# หมายเหตุ: Claude ไม่มี JSON mode บังคับแบบ Gemini/OpenAI ต้องกำชับใน prompt เอง
# และเช็คชื่อโมเดลล่าสุดจาก https://docs.claude.com ก่อนใช้จริง เผื่อมีรุ่นใหม่กว่านี้
# ============================================
def analyze_with_claude(resume_text, job_text, model_name="claude-sonnet-5"):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY — ต้องมี key ก่อนถึงจะเรียกเจ้านี้ได้")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(resume_text, job_text) + "\n\nตอบเป็น JSON ล้วนๆ เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON"

    response = client.messages.create(
        model=model_name,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    # response.content อาจมีหลาย block (ThinkingBlock + TextBlock)
    # ต้องเลือกเฉพาะ block ที่เป็น text จริงๆ ไม่ใช่หยิบ index [0] ตรงๆ
    raw_text = next(
        block.text for block in response.content if block.type == "text"
    )
    return _parse_json_response(raw_text)

# ============================================
# Dispatcher กลาง — full_analysis_pipeline เรียกผ่านตัวนี้ตัวเดียว
# ============================================
PROVIDERS = {
    "gemini": analyze_with_gemini,
    "openai": analyze_with_openai,
    "claude": analyze_with_claude,
}


def analyze_storytelling(resume_text, job_text="", provider="gemini", model_name=None):
    """
    เรียก LLM เจ้าที่เลือกไว้ (provider) วิเคราะห์ storytelling
    คืนค่าเพิ่ม latency_seconds และ provider/model_name ที่ใช้จริง ไว้เทียบกันได้
    """
    if provider not in PROVIDERS:
        raise ValueError(f"ไม่รู้จัก provider '{provider}' — ใช้ได้แค่: {list(PROVIDERS.keys())}")

    fn = PROVIDERS[provider]
    kwargs = {"model_name": model_name} if model_name else {}

    start = time.time()
    result = fn(resume_text, job_text, **kwargs)
    elapsed = round(time.time() - start, 2)

    result["provider"] = provider
    result["latency_seconds"] = elapsed
    return result
