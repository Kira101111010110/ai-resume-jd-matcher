"""
clean_skill_dictionary.py
==========================
แก้ปัญหา noise word หลุดเข้า hard_skills แบบถาวร โดยทำความสะอาดที่ต้นทาง
(dictionary ที่ใช้เทรน skill-extractor-model) แทนการ patch แค่ตอน runtime

วิธีใช้:
    python clean_skill_dictionary.py --input raw_skills.txt --output cleaned_patterns.jsonl

Input format: ไฟล์ text ธรรมดา 1 skill ต่อ 1 บรรทัด
    (ดึงมาจาก resume_data.csv['skills'] + all_job_post.csv['job_skill_set']
     ที่ merge + dedupe แล้วตามที่เคยทำตอนเทรนโมเดล)

Output:
    - cleaned_patterns.jsonl : รายการ skill ที่ผ่านการกรองแล้ว พร้อมเอาไปสร้าง
      spaCy EntityRuler patterns ใหม่ (label: HARD_SKILL / SOFT_SKILL ตามเดิม)
    - review_candidates.csv  : คำที่ "น่าสงสัย" แต่ไม่ได้ตัดอัตโนมัติ ให้คุณ
      รีวิวทีเดียวทั้งชุดแล้วเพิ่มเข้า TIER1_BLOCKLIST เอง (ทำครั้งเดียว จบ)
"""

import argparse
import csv
import json
import re
from wordfreq import zipf_frequency

# ============================================================
# TIER 1: ตัดอัตโนมัติ — มั่นใจสูงว่าไม่ใช่ skill เฉพาะทาง
# แบ่งเป็นหมวดหมู่ เพื่อให้ขยายง่ายและอ่านง่ายกว่า flat list เดิม
# ============================================================

JOB_TITLE_WORDS = {
    "backend", "frontend", "fullstack", "full-stack", "developer", "engineer",
    "manager", "supervisor", "director", "specialist", "analyst", "consultant",
    "coordinator", "administrator", "intern", "trainee", "lead", "senior",
    "junior", "officer", "executive", "assistant",
}

RESUME_SECTION_HEADERS = {
    "objective", "career objective", "summary", "profile", "experience",
    "education", "skills", "certifications", "certification", "projects",
    "project", "references", "reference", "contact", "achievements",
    "achievement", "languages", "language", "awards", "award", "interests",
    "hobbies", "responsibilities", "responsibility", "qualifications",
    "qualification", "personal information", "work experience",
    "professional experience", "career history",
}

GENERIC_PROCESS_WORDS = {
    "engineering", "development", "documentation", "training", "deployment",
    "management", "progress", "project", "programming", "system", "email",
    "team project", "final project", "in progress", "planning", "process",
    "processes", "operations", "operation", "strategy", "strategies",
    "implementation", "maintenance", "support", "solution", "solutions",
    "analysis", "reporting", "report", "reports", "review", "monitoring",
}

# คำที่ตัดสินใจจากรอบ review_hard.csv (247 คำ) — สรุปจากการเปรียบเทียบผล AI
# 2 ตัวที่ประเมินให้ แล้วเลือกใช้เหตุผลที่ตรงกับหลัก resume/skill screening จริง
REVIEWED_BLOCKLIST = {
    "2000", "a/p", "a/r", "ad", "administration", "administrative", "advertising",
    "agency", "aggressive", "agriculture", "ap", "applications", "approach", "army",
    "articles", "assist", "audience", "author", "balance", "banking", "basic",
    "basis", "benefits", "book", "broadcast", "budget", "ca", "cable", "cases",
    "cash", "class", "client", "clients", "closing", "coach", "collection",
    "commitment", "compensation", "competitive", "concept", "confidence", "content",
    "contracts", "cooperation", "council", "credit", "dc", "delivery", "determined",
    "direction", "drawing", "drive", "driven", "drivers", "driving", "economics",
    "edge", "edit", "employment", "engage", "engagement", "enterprise", "epic",
    "equity", "exchange", "fashion", "fast", "features", "feedback", "file",
    "finance", "financial", "flash", "focus", "forms", "frame", "friendly",
    "funds", "g/l", "government", "guidance", "heat", "honest", "increase",
    "independence", "influence", "initiative", "innovation", "inspiration",
    "insurance", "internet", "investigation", "its", "journal", "kind", "law",
    "legal", "letters", "listening", "loans", "m&a", "m&e", "ma", "mail",
    "managing", "manufacturing", "market", "marketing", "marketing/sales",
    "materials", "mechanical", "meetings", "money", "mortgage", "ms", "natural",
    "navy", "next", "numbers", "oil", "organization", "ownership", "page",
    "pages", "paint", "painting", "partnership", "peak", "personnel",
    "philosophy", "pick", "police", "policies", "prime", "producer", "producing",
    "professor", "profit", "promotion", "proposal", "quality", "quick", "read",
    "reading", "receiving", "recording", "reply", "retail", "safety", "sales",
    "san", "scheme", "secretary", "selling", "shipping", "speaker", "speaking",
    "staff", "stories", "strategic", "strategy/planning", "sun", "switch", "tax",
    "taxes", "teaching", "teams", "tear", "technology", "telephone",
    "temperature", "therapy", "trading", "transmission", "transportation",
    "travel", "trend", "trust", "type", "view", "vision", "voice", "website",
    "win", "window", "works", "writer", "writing", "written", "act!",
    # จากตารางเงื่อนไข ที่คำแนะนำสุทธิคือ "ไม่ควรใส่เดี่ยวๆ / ตัดออก"
    "electrical", "hardware", "logic", "memory", "mac", "windows", "apple",
    "iphone", "phone", "phones", "access", "microsoft", "office", "word",
    "presentation", "research", "academic", "physics", "chemistry", "scientific",
    "audio", "camera", "film", "image", "video", "sound", "radio", "tv",
    "television",
}

# รวมทุกหมวดเป็น blocklist เดียว (lowercase ทั้งหมดเพื่อ match แบบ case-insensitive)
TIER1_BLOCKLIST = {
    w.lower() for w in
    (JOB_TITLE_WORDS | RESUME_SECTION_HEADERS | GENERIC_PROCESS_WORDS)
} | REVIEWED_BLOCKLIST

# ============================================================
# WHITELIST: คำ tech ที่บังเอิญเป็นคำ common / สั้น ห้ามตัดทิ้งเด็ดขาด
# (เจอปัญหานี้ตอนทดสอบ: "communication" ต้องเก็บไว้เพราะเป็น soft skill จริง
#  แม้ zipf frequency จะสูงพอๆ กับ noise word)
# ============================================================

TECH_WHITELIST = {
    "go", "r", "c", "swift", "rust", "spark", "hive", "pig", "kafka",
    "docker", "kubernetes", "communication", "leadership", "teamwork",
    "collaboration", "adaptability", "creativity", "empathy",
    # ยืนยันเก็บจากรอบ review 247 คำ (สรุปจากไฟล์ 1 ที่วิเคราะห์ไว้)
    ".net", "3d", "a+", "android", "ann", "architecture", "assembly",
    "c#", "c++", "c/c++", "cloud", "database", "design", "doors",
    "english", "express", "http", "network", "network+", "networks",
    "rest", "script", "security", "security+", "spanish", "spring",
    "statistics", "testing",
}

# threshold: ยิ่งสูงยิ่งเป็นคำ common ในภาษาอังกฤษทั่วไปมาก (สเกล wordfreq ~0-7)
ZIPF_FLAG_THRESHOLD = 4.3

# คำเติมท้าย/นำหน้าที่ทำให้วลีดูเหมือน skill แต่จริงๆ ยังคง generic อยู่
# (เจอปัญหาจริง: "Email support", "Management skills", "Strong management skills"
#  หลุดผ่านการกรองรอบแรกเพราะเป็นวลีหลายคำ ระบบเดิมสมมติว่าวลีหลายคำปลอดภัยเสมอ)
GENERIC_FILLER_WORDS = {
    "strong", "good", "excellent", "basic", "solid", "proven", "skills",
    "skill", "support", "management", "experience", "knowledge", "abilities",
    "ability", "background", "practices", "principles", "and", "of", "in",
    "with", "the", "a", "an", "for",
}


def is_fully_generic_phrase(phrase: str) -> bool:
    """
    เช็คว่าวลีนี้ประกอบด้วยคำ generic/blocklist ล้วนๆ หรือไม่
    (ไม่มีคำเฉพาะทางเจือปนเลยสักคำ) -> ถ้าใช่ ถือว่าทั้งวลีเป็น noise
    """
    tokens = [t.lower().strip(",.()!+") for t in phrase.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    return all(t in TIER1_BLOCKLIST or t in GENERIC_FILLER_WORDS for t in tokens)


def is_multiword(skill: str) -> bool:
    return " " in skill.strip() or "-" in skill.strip()


def classify_skill(skill: str):
    """
    คืนค่า: ('keep' | 'blocked' | 'review', reason)
    """
    raw = skill.strip()
    key = raw.lower()

    if not raw:
        return "blocked", "empty"

    if key in TECH_WHITELIST:
        return "keep", "whitelisted"

    if key in TIER1_BLOCKLIST:
        return "blocked", "tier1_blocklist"

    # วลีหลายคำ: เช็คก่อนว่าเป็นวลีที่ประกอบด้วยคำ generic ล้วนๆ ไหม
    # (เจอจริง: "Email support", "Management skills" หลุดผ่านมาเพราะกฎเดิม
    #  ถือว่าวลีหลายคำปลอดภัยเสมอ ซึ่งไม่จริง)
    if is_multiword(raw):
        if is_fully_generic_phrase(raw):
            return "blocked", "fully_generic_phrase"
        return "keep", "multiword_assumed_safe"

    # คำเดี่ยว: เช็คความถี่ในภาษาอังกฤษทั่วไป
    freq = zipf_frequency(key, "en")
    if freq >= ZIPF_FLAG_THRESHOLD:
        return "review", f"high_zipf_freq={freq}"

    return "keep", "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="raw skill list, 1 ต่อบรรทัด")
    parser.add_argument("--output", default="cleaned_patterns.jsonl")
    parser.add_argument("--review-out", default="review_candidates.csv")
    parser.add_argument("--label", default="HARD_SKILL",
                         help="label ที่จะใส่ใน pattern (HARD_SKILL หรือ SOFT_SKILL)")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        skills = [line.strip() for line in f if line.strip()]

    kept, blocked, review = [], [], []

    for skill in skills:
        status, reason = classify_skill(skill)
        if status == "keep":
            kept.append(skill)
        elif status == "blocked":
            blocked.append((skill, reason))
        else:
            review.append((skill, reason))

    # เขียน patterns file สำหรับ spaCy EntityRuler
    with open(args.output, "w", encoding="utf-8") as f:
        for skill in sorted(set(kept)):
            pattern = {"label": args.label, "pattern": skill}
            f.write(json.dumps(pattern, ensure_ascii=False) + "\n")

    # เขียนรายงานคำที่ต้องรีวิว (ทำครั้งเดียว ไม่ต้องรอเจอทีละใบอีก)
    with open(args.review_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["skill", "reason", "decision (keep/block - กรอกเอง)"])
        for skill, reason in sorted(review, key=lambda x: x[0].lower()):
            writer.writerow([skill, reason, ""])

    print(f"รวม input: {len(skills)} skills")
    print(f"เก็บไว้ (auto): {len(set(kept))}")
    print(f"ตัดทิ้ง (auto, tier1 blocklist): {len(blocked)}")
    print(f"ต้องรีวิว (high freq, ไม่แน่ใจ): {len(review)}")
    print(f"\n-> เปิด {args.review_out} เช็คคอลัมน์ decision แล้วเติม keep/block")
    print(f"   จากนั้นเอา skill ที่ decision=block ไปเพิ่มใน TIER1_BLOCKLIST")
    print(f"   ในสคริปต์นี้ แล้วรันใหม่อีกรอบก่อนเทรนโมเดลจริง")


if __name__ == "__main__":
    main()
