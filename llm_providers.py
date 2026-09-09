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

STORYTELLING_PROMPT_TEMPLATE = """วิเคราะห์ resume ต่อไปนี้ 2 ส่วนแยกจากกันอย่างชัดเจน:
(1) วิเคราะห์คุณภาพของ resume โดยรวม (การเล่าเรื่องแบบ Problem → Action → Result)
(2) วิเคราะห์เทียบกับรายละเอียดงาน (Job Description) ที่สมัครโดยเฉพาะ
ห้ามปนสองส่วนนี้เข้าด้วยกัน เพราะผู้สมัครและ HR จะเห็นสองส่วนนี้แยกกันคนละจุดในหน้าจอ

กฎการใช้คำ (สำคัญมาก — ใช้กับทุก key ที่เป็นข้อความคำตอบ): ห้ามใช้คำย่อ "JD" ในคำตอบเด็ดขาด
เพราะผู้ใช้ทั่วไปอ่านแล้วไม่เข้าใจ ให้ใช้คำว่า "รายละเอียดงาน" แทนทุกครั้ง (คำว่า "JD" ในพรอมต์นี้ใช้เพื่อความกระชับ
ในการอธิบายเกณฑ์ให้คุณเข้าใจเท่านั้น ไม่ใช่คำที่ควรปรากฏในคำตอบ)

Resume:
{resume_text}

{job_title_line}

{job_line}

{faculty_line}

{matching_score_line}

เกณฑ์การประเมิน faculty_match (คณะ/สาขาที่จบ ของผู้สมัคร เทียบกับ "คณะ/สาขาที่ต้องการ" ที่ระบุไว้ด้านบน — ห้ามเทียบกับรายละเอียดงาน):
- "ตรง" = สาขาตรงกันชัดเจนหรือเป็นสาขาเดียวกัน
- "ใกล้เคียง" = สาขาที่เกี่ยวข้องกันแต่ไม่ตรงเป๊ะ (เช่น วิศวกรรมคอมพิวเตอร์ กับ วิทยาการคอมพิวเตอร์)
- "ไม่ตรง" = คนละสายกันชัดเจน (เช่น สายการเงิน กับ สายวิศวกรรม)
- "ไม่ระบุ" = ไม่มีการระบุ "คณะ/สาขาที่ต้องการ" มาให้ (ไม่ใช่ดูจากรายละเอียดงาน) หรือ resume ไม่ได้ระบุคณะ/สาขาที่จบ

เกณฑ์การประเมิน recommendation_reason (ควรรับผู้สมัครคนนี้เข้าสู่กระบวนการต่อไปหรือไม่ — เป็นภาพรวมสุดท้ายจากทุกปัจจัย นี่คือ "คำแนะนำเบื้องต้น" ให้ HR ใช้ประกอบการตัดสินใจ ไม่ใช่คำตัดสินสุดท้าย เพราะ HR ยังต้องพิจารณาปัจจัยอื่นเพิ่ม เช่น การสัมภาษณ์):
- ก่อนตัดสินใจ ให้ประเมินสัดส่วนทักษะที่ resume มีจริงเทียบกับทักษะทั้งหมดที่รายละเอียดงานระบุว่าต้องการ (ประมาณเป็น % คร่าวๆ จากการอ่านทั้งสองฝั่ง) แล้วใช้ตัวเลขนี้เป็นหลักฐานหลักประกอบการตัดสินใจ ไม่ใช่แค่ความรู้สึกกว้างๆ ว่า "พอมีทักษะตรง"
- เกณฑ์คร่าวๆ ตามสัดส่วนทักษะที่ตรง (ปรับได้ตามบริบท ไม่ใช่กฎตายตัว): ต่ำกว่า 40% ควรเอนเอียงไปทาง "ไม่ควรรับ" เว้นแต่มีปัจจัยอื่นชดเชยชัดเจนมาก (เช่น โปรเจกต์ตรงกับงานมาก หรือทักษะที่ขาดเป็นทักษะเสริมไม่ใช่ทักษะหลักที่รายละเอียดงานเน้น) / 40-70% ให้ชั่งน้ำหนักกับคุณภาพ resume และความสอดคล้องคณะ/สาขาประกอบด้วย / สูงกว่า 70% ควรเอนเอียงไปทาง "ควรรับ" เว้นแต่มีปัญหาสำคัญด้านอื่นชัดเจน (เช่น คนละสายงานกับคณะที่จบสิ้นเชิง)
- ให้ชั่งน้ำหนักรวมทั้งหมด: สัดส่วนทักษะที่ตรงกับรายละเอียดงาน (ตามเกณฑ์ข้างต้น), คุณภาพการนำเสนอ/ประสบการณ์ใน resume, ความสอดคล้องของคณะ/สาขา (ถ้ามีการระบุมา), คะแนนความคล้ายเชิงความหมายจากระบบ (ดูคำอธิบายช่วงค่าด้านบน — เป็นสัญญาณเสริม ไม่ใช่ตัวตัดสินหลัก), และภาพรวมว่า resume นี้เหมาะกับตำแหน่งนี้แค่ไหน
- ถ้ามีการระบุ "ชื่อตำแหน่งงาน" มาด้านบน ให้ใช้ประกอบการพิจารณาระดับประสบการณ์ที่คาดหวังด้วยเสมอ เช่น ถ้าชื่อตำแหน่งสื่อถึงระดับอาวุโส (Senior/Lead/Manager) ต้องเช็คว่า resume มีประสบการณ์ระดับนั้นจริงไหม ไม่ใช่แค่มีทักษะตรงกับรายละเอียดงานผิวเผิน — ถ้าชื่อตำแหน่งบ่งบอกระดับเริ่มต้น (Junior/Intern/Entry-level) ก็ไม่ควรตัดสิทธิ์ผู้สมัครที่ประสบการณ์ยังน้อยอยู่
- ถ้าชื่อตำแหน่งงานกับเนื้อหาในรายละเอียดงานดูขัดแย้งกันเอง (เช่น ชื่อตำแหน่งบอก Senior แต่เนื้อหารายละเอียดงานเขียนคุณสมบัติระดับเริ่มต้นล้วนๆ) ให้สังเกตความขัดแย้งนี้ไว้ประกอบการตัดสินใจด้วย
- ต้องตัดสินใจให้ชัดเจน เจาะจง ไม่คลุมเครือ ไม่ใช้คำกำกวมที่ตีความได้สองทาง (เช่น ห้ามตอบแบบ "อาจจะพิจารณาได้บ้าง") และต้องเข้มงวดกว่าการประเมิน specific_strengths — อย่าตัดสินว่า "ควรรับ" ง่ายเกินไปเพียงเพราะมีทักษะตรงบางส่วน ต้องดูสัดส่วนโดยรวมจริงๆ
- ขึ้นต้นด้วย "ควรรับ" ถ้าผู้สมัครมีจุดที่น่าสนใจมากพอที่ HR ควรพิจารณาต่อ (ไม่จำเป็นต้องสมบูรณ์แบบทุกด้าน)
- ขึ้นต้นด้วย "ไม่ควรรับ" ถ้าขาดคุณสมบัติสำคัญไปมาก หรือคนละสายงานกันชัดเจนจน HR ไม่ควรเสียเวลาพิจารณาต่อ
- ห้ามตัดสินแบบเดา ต้องมีเหตุผลรองรับตามด้วยเสมอ และควรระบุสัดส่วนทักษะที่ประเมินได้ไว้ในเหตุผลสั้นๆ ด้วย (เช่น "ทักษะตรงกับรายละเอียดงานประมาณ 60%")

สำคัญมาก: ต้องตอบ JSON ให้ครบทุก key ด้านล่างนี้เสมอ ห้ามละเว้น key ใดแม้จะไม่มีข้อมูล
(ถ้าไม่มีข้อมูลให้ใส่ "ไม่ระบุ" หรือ null ตามชนิดของ key นั้น ไม่ใช่ตัดทิ้งทั้ง key)

ตอบเป็น JSON เท่านั้น ในรูปแบบนี้:
{{
  "storytelling_score": "High" หรือ "Medium" หรือ "Low",
  "ai_reason": "[ส่วนที่ 1: วิเคราะห์ resume โดยรวมเท่านั้น] สรุปสั้นๆ ภาษาไทย ไม่เกิน 1 ประโยค (ไม่เกิน 25 คำ) พูดจุดเด่นหรือจุดที่ควรปรับปรุงของการนำเสนอตัวเองใน resume แค่ประเด็นเดียวที่สำคัญที่สุด ใช้ภาษาง่ายๆ อ่านแล้วเข้าใจทันที ห้ามพูดถึงหรือเปรียบเทียบกับรายละเอียดงานในส่วนนี้เด็ดขาด",
  "quantified_results_count": จำนวนเต็ม 0 ถึง 5+ — นับจำนวนจุดในเรซูเม่ที่มีผลลัพธ์เป็นตัวเลขวัดผลได้จริง (เช่น 'ลด error 35%', 'ดูแลผู้ใช้ 500 คน') แต่ละจุดนับ 1 ห้ามนับซ้ำจุดเดิม ถ้าไม่มีเลยให้ใส่ 0,
  "strengths": ["จุดแข็ง 1", "จุดแข็ง 2"],
  "weaknesses": ["จุดที่ควรปรับปรุง 1"],
  "specific_strengths": "[ส่วนที่ 2: วิเคราะห์เทียบรายละเอียดงานเท่านั้น] ถ้ามีรายละเอียดงานด้านบน ให้เปรียบเทียบตรงๆ ว่าผู้สมัครเหมาะกับตำแหน่งนี้แค่ไหน โดยระบุจุดที่ตรงกันจริง (ทักษะ/ประสบการณ์/ผลงานที่ resume มีและรายละเอียดงานต้องการ) และจุดที่ resume ยังขาดหรือไม่ตรงกับรายละเอียดงาน เป็นภาษาไทย 2-3 ประโยค **ต้องตรวจดู resume ด้วยว่ามีการพูดถึงโปรเจกต์ (project/portfolio) หรือไม่ ถ้ามี ให้ระบุชื่อ/ลักษณะโปรเจกต์นั้นและประเมินว่าเกี่ยวข้องกับตำแหน่งงานนี้โดยตรงแค่ไหน (เช่น สร้างด้วยเทคโนโลยีเดียวกับที่รายละเอียดงานต้องการ หรือแก้ปัญหาลักษณะเดียวกัน) ถ้า resume ไม่มีโปรเจกต์เลยให้ระบุว่าขาดผลงานที่แสดงฝีมือจริง หากมีการระบุ 'ชื่อตำแหน่งงาน' มาด้วย ให้พิจารณาระดับประสบการณ์ของผู้สมัครเทียบกับระดับที่ชื่อตำแหน่งนั้นสื่อถึงด้วย (เช่น Senior ต้องมีประสบการณ์เชิงลึกจริง ไม่ใช่แค่เคยใช้เทคโนโลยีนั้นผิวเผิน)** ถ้าไม่มีรายละเอียดงานให้ตอบว่า 'ไม่สามารถวิเคราะห์เทียบรายละเอียดงานได้ เนื่องจากไม่มีการระบุรายละเอียดงาน' เท่านั้น ห้ามเปลี่ยนไปพูดจุดเด่นทั่วไปของผู้สมัครแทนโดยเด็ดขาด (จุดเด่นทั่วไปให้ไปอยู่ใน ai_reason แทน)",
  "faculty_match": "1 ประโยค ภาษาไทย ขึ้นต้นด้วยคำว่า 'ตรง เพราะ' หรือ 'ใกล้เคียง เพราะ' หรือ 'ไม่ตรง เพราะ' หรือ 'ไม่ระบุ เพราะ' ตามเกณฑ์ด้านบน (เทียบกับคณะ/สาขาที่ต้องการที่ระบุไว้ ไม่ใช่รายละเอียดงาน) แล้วตามด้วยเหตุผลสั้นๆ",
  "recommendation_reason": "1 ประโยค ภาษาไทย ขึ้นต้นด้วยคำว่า 'ควรรับ เพราะ' หรือ 'ไม่ควรรับ เพราะ' ตามเกณฑ์ recommendation_reason ด้านบน แล้วตามด้วยเหตุผลสั้นๆ",
  "confidence": ตัวเลข 0.0 ถึง 1.0 แสดงความมั่นใจของคุณเองในการวิเคราะห์นี้
}}"""


def _build_prompt(resume_text, job_text, required_faculty=None, job_title=None, raw_matching_score=None):
    job_title_line = (
        f"ชื่อตำแหน่งงานที่เปิดรับ (ระบุมาจากระบบโดยตรง): {job_title}"
        if job_title
        else "ชื่อตำแหน่งงาน: ไม่ได้ระบุมาจากระบบ ให้ดูจากรายละเอียดงานด้านล่างแทน"
    )
    job_line = f"รายละเอียดงานที่สมัคร: {job_text}" if job_text else ""
    faculty_line = (
        f"คณะ/สาขาที่ต้องการสำหรับตำแหน่งนี้ (ระบุมาจากระบบโดยตรง ไม่ใช่ตีความจากรายละเอียดงาน): {required_faculty}"
        if required_faculty
        else "คณะ/สาขาที่ต้องการ: ไม่ได้ระบุมาจากระบบ"
    )
    matching_score_line = (
        f"คะแนนความคล้ายเชิงความหมายระหว่าง resume กับรายละเอียดงานจากระบบวัดอัตโนมัติ (SBERT): {raw_matching_score}/100 "
        f"— ใช้เป็น 'สัญญาณเสริม' เท่านั้น ห้ามใช้ตัดสินหลัก เพราะค่านี้มีลักษณะพิเศษ: "
        f"แม้ resume ที่เหมาะสมกับตำแหน่งนี้มากจริงๆ ก็มักได้แค่ 40-70 คะแนน ไม่ค่อยเกิน 70 "
        f"(ต่างจาก % ทักษะที่คุณประเมินเองซึ่งพุ่งสูงกว่านี้ได้ปกติ) ดังนั้นห้ามตีความว่าต่ำกว่า 70 = แย่ "
        f"ให้ใช้แค่เป็นแนวโน้มคร่าวๆ ประกอบ เช่น ถ้าคะแนนนี้ต่ำมากๆ (ต่ำกว่า 20) ร่วมกับสัญญาณอื่นที่บอกว่าไม่ตรงกัน "
        f"ก็เป็นหลักฐานเสริมว่าคนละสายงานกันจริง"
        if raw_matching_score is not None
        else "คะแนนความคล้ายเชิงความหมาย (SBERT): ไม่มีข้อมูล"
    )
    return STORYTELLING_PROMPT_TEMPLATE.format(
        resume_text=resume_text, job_title_line=job_title_line, job_line=job_line,
        faculty_line=faculty_line, matching_score_line=matching_score_line
    )


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
        result.setdefault("faculty_match", "ไม่ระบุ เพราะไม่มีข้อมูลเพียงพอ")
        result.setdefault("recommendation_reason", "ไม่ระบุ เพราะไม่มีข้อมูลเพียงพอสำหรับสรุปคำแนะนำ")
        result.setdefault("quantified_results_count", 0)
        result["json_valid"] = True
        return result
    except json.JSONDecodeError:
        return {
            "storytelling_score": None,
            "ai_reason": None,
            "specific_strengths": None,
            "faculty_match": "ไม่ระบุ เพราะไม่มีข้อมูลเพียงพอ",
            "recommendation_reason": "ไม่ระบุ เพราะประมวลผลคำตอบจาก AI ไม่สำเร็จ",
            "quantified_results_count": 0,
            "confidence": 0.0,
            "json_valid": False,
            "raw_response": raw_text
        }


# ============================================
# Gemini (ใช้งานได้จริง มี API key แล้ว)
# ============================================
def analyze_with_gemini(resume_text, job_text, required_faculty=None, job_title=None, raw_matching_score=None, model_name="gemini-3.6-flash"):
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel(model_name)
    prompt = _build_prompt(resume_text, job_text, required_faculty, job_title, raw_matching_score)

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
def analyze_with_openai(resume_text, job_text, required_faculty=None, job_title=None, raw_matching_score=None, model_name="gpt-5.6-luna"):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า OPENAI_API_KEY — ต้องมี key ก่อนถึงจะเรียกเจ้านี้ได้")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(resume_text, job_text, required_faculty, job_title, raw_matching_score)

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
def analyze_with_claude(resume_text, job_text, required_faculty=None, job_title=None, raw_matching_score=None, model_name="claude-sonnet-5"):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY — ต้องมี key ก่อนถึงจะเรียกเจ้านี้ได้")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(resume_text, job_text, required_faculty, job_title, raw_matching_score) + "\n\nตอบเป็น JSON ล้วนๆ เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON"

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


def analyze_storytelling(resume_text, job_text="", required_faculty=None, job_title=None, raw_matching_score=None, provider="gemini", model_name=None):
    """
    เรียก LLM เจ้าที่เลือกไว้ (provider) วิเคราะห์ storytelling
    required_faculty: คณะ/สาขาที่ต้องการ ส่งมาจาก backend ตรงๆ (เช่น post.faculty)
    ใช้เทียบ faculty_match กับ resume โดยตรง — ไม่ใช่ให้ LLM เดาจาก job_text/JD
    job_title: ชื่อตำแหน่งงานที่เปิดรับ ส่งมาจาก backend ตรงๆ (เช่น post.title)
    ช่วยให้ LLM รู้ตำแหน่งชัดเจน ไม่ต้องเดาจาก job_text/JD อย่างเดียว
    raw_matching_score: คะแนน SBERT ดิบ (ก่อนหัก penalty) ส่งเข้าไปเป็นสัญญาณเสริมให้ recommendation_reason
    (ใช้ raw ไม่ใช่ matching_score ตัวสุดท้าย เพราะตัวสุดท้ายคำนวณหลังเรียก LLM นี้เสร็จ — ยังไม่มีตอนนี้)
    คืนค่าเพิ่ม latency_seconds และ provider/model_name ที่ใช้จริง ไว้เทียบกันได้
    """
    if provider not in PROVIDERS:
        raise ValueError(f"ไม่รู้จัก provider '{provider}' — ใช้ได้แค่: {list(PROVIDERS.keys())}")

    fn = PROVIDERS[provider]
    kwargs = {"model_name": model_name} if model_name else {}

    start = time.time()
    result = fn(resume_text, job_text, required_faculty, job_title, raw_matching_score, **kwargs)
    elapsed = round(time.time() - start, 2)

    result["provider"] = provider
    result["latency_seconds"] = elapsed
    return result
