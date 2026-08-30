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
    expected_skills = max(word_count / 20, 1)
    coverage = min(total_skills / expected_skills, 1.0)

    if total_skills == 0:
        precision_estimate = 0.0
    else:
        non_generic = [s for s in all_skills if s.lower() not in GENERIC_ROLE_WORDS]
        precision_estimate = len(non_generic) / total_skills

    confidence = round(0.5 * coverage + 0.5 * precision_estimate, 2)
    return confidence


def full_analysis_pipeline(resume_text, job_text, model_provider="gemini", model_name=None):
    """
    model_provider: "gemini" | "openai" | "claude" — เลือกเจ้าที่จะใช้วิเคราะห์ storytelling
    model_name: ชื่อรุ่นเฉพาะของเจ้านั้น (ถ้าไม่ระบุ ใช้ค่า default ของแต่ละเจ้า)
    """
    # --- SBERT matching (ไม่เกี่ยวกับการเลือก LLM) ---
    matching_score = get_matching_score(resume_text, job_text)
    matching_confidence = calculate_matching_confidence(matching_score)

    # --- Skill extraction (ไม่เกี่ยวกับการเลือก LLM) ---
    raw_skills = extract_skills(resume_text)
    skill_extraction_confidence = calculate_skill_extraction_confidence(raw_skills, resume_text)
    clean_skills = filter_generic_skills(raw_skills)

    # --- Storytelling: ใช้ provider ที่เลือกไว้ ---
    storytelling_result = analyze_storytelling(
        resume_text, job_text, provider=model_provider, model_name=model_name
    )
    storytelling_confidence = storytelling_result.get("confidence", 0.0)

    # --- Overall confidence: weighted average ---
    overall_confidence = round(
        0.4 * matching_confidence +
        0.3 * skill_extraction_confidence +
        0.3 * storytelling_confidence,
        2
    )

    return {
        "matching_score": matching_score,
        "matching_confidence": matching_confidence,

        "skills": {
            "hard": clean_skills["hard_skills"],
            "soft": clean_skills["soft_skills"]
        },
        "skill_extraction_confidence": skill_extraction_confidence,

        "storytelling_score": storytelling_result.get("storytelling_score"),
        "ai_reason": storytelling_result.get("ai_reason"),
        "specific_strengths": storytelling_result.get("specific_strengths"),
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

    result = full_analysis_pipeline(test_resume, test_job, model_provider="gemini")
    print(json.dumps(result, indent=2, ensure_ascii=False))
