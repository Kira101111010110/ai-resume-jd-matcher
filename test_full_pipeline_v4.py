from sentence_transformers import SentenceTransformer, util
import spacy
import json
from llm_providers import analyze_storytelling

# ============================================
# 1. โหลดโมเดลทั้งหมด (ทำครั้งเดียวตอนเริ่มโปรแกรม)
# ============================================
print("กำลังโหลดโมเดล...")
sbert_model = SentenceTransformer('./resume-jd-matcher-model/resume-jd-matcher')
nlp = spacy.load('./skill-extractor-model')
print("โหลดโมเดลเสร็จแล้ว\n")

GENERIC_ROLE_WORDS = {
    # job title / role คำทั่วไป
    "backend", "frontend", "developer", "engineer", "manager", "engineering",
    "development", "documentation", "training", "deployment",
    # คำที่หลุดมาจาก label/หัวข้ออื่นๆ ใน resume ไม่ใช่ skill จริง
    "email", "management", "progress", "project", "programming", "system",
    "team project", "final project", "in progress",
}


# ============================================
# 2. ฟังก์ชันแต่ละส่วน
# ============================================
def extract_skills(text):
    doc = nlp(text)
    hard = sorted(set(ent.text for ent in doc.ents if ent.label_ == "HARD_SKILL"))
    soft = sorted(set(ent.text for ent in doc.ents if ent.label_ == "SOFT_SKILL"))
    return {"hard_skills": hard, "soft_skills": soft}


def filter_generic_skills(raw_skills):
    hard_filtered = [s for s in raw_skills["hard_skills"] if s.lower() not in GENERIC_ROLE_WORDS]
    soft_filtered = [s for s in raw_skills["soft_skills"] if s.lower() not in GENERIC_ROLE_WORDS]
    return {"hard_skills": hard_filtered, "soft_skills": soft_filtered}


def get_matching_score(resume_text, job_text):
    emb1 = sbert_model.encode(resume_text)
    emb2 = sbert_model.encode(job_text)
    return round(util.cos_sim(emb1, emb2).item() * 100, 1)


def calculate_matching_confidence(matching_score):
    distance = abs(matching_score - 50) / 50
    return round(distance, 2)


def calculate_skill_extraction_confidence(raw_skills, resume_text):
    hard = raw_skills.get("hard_skills", [])
    soft = raw_skills.get("soft_skills", [])
    all_skills = hard + soft
    total_skills = len(all_skills)

    word_count = max(len(resume_text.split()), 1)
    # หารด้วย 12 แทน 20 (เดิม) — ทำให้ต้องมีทักษะเยอะขึ้นเทียบกับความยาว resume ถึงจะแตะ coverage เต็ม 1.0
    # กันไม่ให้ resume ที่แค่ "ยาว" หรือ "ยัดทักษะเยอะๆ" ได้คะแนนเต็มง่ายเกินไป
    expected_skills = max(word_count / 12, 1)
    coverage = min(total_skills / expected_skills, 1.0)

    if total_skills == 0:
        precision_estimate = 0.0
    else:
        non_generic = [s for s in all_skills if s.lower() not in GENERIC_ROLE_WORDS]
        precision_estimate = len(non_generic) / total_skills

    confidence = round(0.5 * coverage + 0.5 * precision_estimate, 2)
    return confidence


VALID_FACULTY_STATUSES = {"ตรง", "ใกล้เคียง", "ไม่ตรง", "ไม่ระบุ"}


def normalize_faculty_match(faculty_match):
    """กัน LLM ตอบไม่ขึ้นต้นด้วย 4 คำที่กำหนด (เช่น ตอบเพี้ยน หรือว่าง)
    เพื่อความสม่ำเสมอของข้อมูลที่ส่งออกไปให้ backend"""
    if not isinstance(faculty_match, str) or not any(
        faculty_match.strip().startswith(s) for s in VALID_FACULTY_STATUSES
    ):
        return "ไม่ระบุ เพราะไม่มีข้อมูลเพียงพอ"
    return faculty_match.strip()


VALID_RECOMMENDATION_STATUSES = {"ควรรับ", "ไม่ควรรับ", "ไม่ระบุ"}


def normalize_recommendation_reason(recommendation_reason):
    """กัน LLM ตอบไม่ขึ้นต้นด้วยคำที่กำหนด — เหมือน normalize_faculty_match
    เพื่อให้ frontend อ่านคำตัดสิน (ควร/ไม่ควรพิจารณา) จากต้นข้อความได้ทันที โดยไม่ต้อง field แยก"""
    if not isinstance(recommendation_reason, str) or not any(
        recommendation_reason.strip().startswith(s) for s in VALID_RECOMMENDATION_STATUSES
    ):
        return "ไม่ระบุ เพราะไม่มีข้อมูลเพียงพอ"
    return recommendation_reason.strip()


# ============================================
# Penalty สำหรับ matching_score เมื่อคณะ/สาขาหรือทักษะไม่ตรงกับ JD
# (SBERT cosine similarity ล้วนๆ จับ "โครงสร้างประโยคทางการ" ได้ ทำให้คะแนนสูงเกินจริง
#  แม้เนื้อหาจะคนละสายงานสิ้นเชิง — ใช้สัญญาณที่ pipeline มีอยู่แล้วมาคูณลดคะแนน)
# ============================================
FACULTY_PENALTY_MULTIPLIER = {
    "ตรง": 1.0,
    "ใกล้เคียง": 0.85,
    "ไม่ตรง": 0.4,
    "ไม่ระบุ": 1.0,   # ไม่มีข้อมูลพอจะตัดสิน ไม่ควรลงโทษ
}


def get_faculty_penalty(faculty_match_normalized):
    for status, multiplier in FACULTY_PENALTY_MULTIPLIER.items():
        if faculty_match_normalized.startswith(status):
            return multiplier, status
    return 1.0, "ไม่ระบุ"


def calculate_skill_overlap(resume_skills, job_skills):
    """สัดส่วนทักษะที่ JD ต้องการ แล้ว resume มีจริง (0.0-1.0)
    None ถ้าดึงทักษะจาก JD ไม่ได้เลย (ไม่มีฐานให้เทียบ)"""
    resume_set = {s.lower() for s in resume_skills.get("hard_skills", []) + resume_skills.get("soft_skills", [])}
    job_set = {s.lower() for s in job_skills.get("hard_skills", []) + job_skills.get("soft_skills", [])}
    if not job_set:
        return None
    matched = resume_set & job_set
    return round(len(matched) / len(job_set), 3)


def get_skill_penalty(skill_overlap_ratio):
    if skill_overlap_ratio is None:
        return 1.0   # ดึงทักษะจาก JD ไม่ได้ ไม่ควรลงโทษ
    if skill_overlap_ratio >= 0.5:
        return 1.0
    if skill_overlap_ratio >= 0.2:
        return 0.8
    return 0.6


def adjust_matching_score(raw_score, faculty_penalty, skill_penalty):
    total_penalty = round(faculty_penalty * skill_penalty, 3)
    adjusted = round(raw_score * total_penalty, 1)
    return adjusted, total_penalty


# ============================================
# คะแนนคุณภาพเรซูเม่ของผู้สมัครเอง — ไม่เทียบกับ Job Description เลย
# (ให้โชว์ฝั่งผู้สมัคร คู่กับ specific_strengths ที่เป็นความสอดคล้องกับตำแหน่งงาน)
# ============================================
STORYTELLING_SCORE_MAP = {"High": 100, "Medium": 60, "Low": 30}


def calculate_resume_quality_score(skill_extraction_confidence, storytelling_score, storytelling_raw_confidence, quantified_results_count):
    """
    คะแนนคุณภาพ resume ของผู้สมัครเอง — ไม่เทียบกับ Job Description เลย
    คำนวณจาก 3 อย่างที่ไม่ขึ้นกับ JD: ความชัดเจนของทักษะที่สกัดได้, คุณภาพการเล่าเรื่อง (ผสม bucket
    กับ confidence ดิบของ LLM กันคะแนนกระจุกตัวที่ 100), และจำนวนจุดที่มีผลลัพธ์วัดผลได้จริง (ไล่ระดับ 0-3+)
    """
    storytelling_bucket = STORYTELLING_SCORE_MAP.get(storytelling_score, 30)
    storytelling_component = 0.6 * storytelling_bucket + 0.4 * (storytelling_raw_confidence * 100)

    quantified_component = min(quantified_results_count, 3) / 3 * 100

    score = (
        0.4 * (skill_extraction_confidence * 100) +
        0.4 * storytelling_component +
        0.2 * quantified_component
    )
    return round(score, 1)


def full_analysis_pipeline(resume_text, job_text, required_faculty=None, job_title=None, model_provider="gemini", model_name=None):
    """
    required_faculty: คณะ/สาขาที่ต้องการสำหรับตำแหน่งนี้ ส่งมาจาก backend ตรงๆ (เช่น post.faculty)
        ใช้เทียบ faculty_match กับ resume โดยตรง — ไม่ใช่ให้ LLM เดาจาก job_text/JD
    job_title: ชื่อตำแหน่งงานที่เปิดรับ ส่งมาจาก backend ตรงๆ (เช่น post.title)
        ช่วยให้ LLM รู้ตำแหน่งชัดเจน ไม่ต้องเดาจาก job_text/JD อย่างเดียว
    model_provider: "gemini" | "openai" | "claude" — เลือกเจ้าที่จะใช้วิเคราะห์ storytelling
    model_name: ชื่อรุ่นเฉพาะของเจ้านั้น (ถ้าไม่ระบุ ใช้ค่า default ของแต่ละเจ้า)
    """
    # --- SBERT matching (ไม่เกี่ยวกับการเลือก LLM) ---
    raw_matching_score = get_matching_score(resume_text, job_text)

    # --- Skill extraction (ไม่เกี่ยวกับการเลือก LLM) ---
    raw_skills = extract_skills(resume_text)
    skill_extraction_confidence = calculate_skill_extraction_confidence(raw_skills, resume_text)
    clean_skills = filter_generic_skills(raw_skills)

    # --- Skill extraction ฝั่ง JD ด้วย (ใช้เฉพาะคำนวณ skill_overlap_ratio ไม่ได้เอาไปโชว์) ---
    job_raw_skills = extract_skills(job_text)
    skill_overlap_ratio = calculate_skill_overlap(raw_skills, job_raw_skills)
    skill_penalty = get_skill_penalty(skill_overlap_ratio)

    # --- Storytelling: ใช้ provider ที่เลือกไว้ ---
    storytelling_result = analyze_storytelling(
        resume_text, job_text, required_faculty=required_faculty, job_title=job_title,
        raw_matching_score=raw_matching_score,
        provider=model_provider, model_name=model_name
    )
    storytelling_confidence = storytelling_result.get("confidence", 0.0)

    # --- ปรับ matching_score ลงตาม faculty_match + skill_overlap ---
    # (แก้ปัญหา: SBERT คะแนนสูงเกินจริงเวลาคนละสายงาน เพราะจับแค่ "โครงสร้างประโยคทางการ" ได้)
    faculty_match_normalized = normalize_faculty_match(storytelling_result.get("faculty_match"))
    faculty_penalty, faculty_status = get_faculty_penalty(faculty_match_normalized)
    matching_score, matching_penalty_multiplier = adjust_matching_score(
        raw_matching_score, faculty_penalty, skill_penalty
    )
    matching_confidence = calculate_matching_confidence(matching_score)

    # --- Resume quality score: คะแนนคุณภาพ resume ล้วนๆ ไม่เทียบกับ JD (สำหรับโชว์ฝั่งผู้สมัคร) ---
    resume_quality_score = calculate_resume_quality_score(
        skill_extraction_confidence,
        storytelling_result.get("storytelling_score"),
        storytelling_confidence,
        storytelling_result.get("quantified_results_count", 0)
    )

    # --- Overall confidence: weighted average ---
    overall_confidence = round(
        0.4 * matching_confidence +
        0.3 * skill_extraction_confidence +
        0.3 * storytelling_confidence,
        2
    )

    return {
        "matching_score": matching_score,
        "raw_matching_score": raw_matching_score,
        "matching_penalty_multiplier": matching_penalty_multiplier,
        "skill_overlap_ratio": skill_overlap_ratio,
        "matching_confidence": matching_confidence,
        "resume_quality_score": resume_quality_score,

        "skills": {
            "hard": clean_skills["hard_skills"],
            "soft": clean_skills["soft_skills"]
        },
        "skill_extraction_confidence": skill_extraction_confidence,

        "storytelling_score": storytelling_result.get("storytelling_score"),
        "ai_reason": storytelling_result.get("ai_reason"),
        "specific_strengths": storytelling_result.get("specific_strengths"),
        "faculty_match": normalize_faculty_match(storytelling_result.get("faculty_match")),
        "recommendation_reason": normalize_recommendation_reason(storytelling_result.get("recommendation_reason")),
        "storytelling_confidence": storytelling_confidence,
        "storytelling_provider": storytelling_result.get("provider"),
        "storytelling_latency_seconds": storytelling_result.get("latency_seconds"),

        "overall_confidence": overall_confidence
    }


# ============================================
# 3. ทดสอบจริง
# ============================================
if __name__ == "__main__":
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

    print("=" * 60)
    print("กำลังวิเคราะห์ (provider=gemini)...")
    print("=" * 60)

    result = full_analysis_pipeline(
        test_resume, test_job,
        required_faculty="วิศวกรรมคอมพิวเตอร์",
        model_provider="gemini"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
