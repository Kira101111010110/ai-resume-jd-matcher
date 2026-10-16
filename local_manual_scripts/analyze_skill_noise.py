# -*- coding: utf-8 -*-
"""
สคริปต์วิเคราะห์ผลกระทบของการแก้ test_full_pipeline_v4.py (skill_overlap_ratio ใช้ clean_skills
ทั้ง 2 ฝั่ง + เพิ่ม noise words ลง GENERIC_ROLE_WORDS) เทียบกับพฤติกรรมเดิมก่อนแก้
"old" ด้านล่าง = จำลองพฤติกรรมเดิมก่อนแก้ (raw_skills ดิบทั้ง 2 ฝั่ง + GENERIC_ROLE_WORDS ชุดเดิม 19 คำ)
"new" ด้านล่าง = เรียกฟังก์ชันจริงจาก test_full_pipeline_v4.py ที่แก้แล้ว (ยืนยันว่า production ทำงานตรงตามที่ออกแบบไว้)

วิธีรัน: ต้องรันจาก root ของ repo เท่านั้น (ไม่ใช่จากใน local_manual_scripts/)
    cd <repo root>
    python local_manual_scripts/analyze_skill_noise.py
เหตุผล: ไฟล์นี้ import test_full_pipeline_v4.py ซึ่งโหลดโมเดล SBERT ด้วย relative path
('./resume-jd-matcher-model/...') ที่ผูกกับ working directory ตอนรัน ไม่ใช่ตำแหน่งไฟล์ — เป็นพฤติกรรม
เดิมของ test_full_pipeline_v4.py ไม่ได้แก้ตรงนี้
"""

import os
import sys
import json
import glob

# เพิ่ม root ของ repo เข้า sys.path เพราะไฟล์นี้อยู่ใน local_manual_scripts/ ไม่ใช่ root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
import pdf_extraction as pe
from test_full_pipeline_v4 import (
    extract_skills,
    filter_generic_skills,
    calculate_skill_overlap,
    get_skill_penalty,
    GENERIC_ROLE_WORDS as NEW_GENERIC_ROLE_WORDS,  # ชุดที่แก้แล้ว (24 คำ) — ใช้ยืนยันว่ามี noise words ครบ
)

EXPECTED_NEW_WORDS = {"software engineer", "data analyst", "insight", "hr", "hiring"}
assert EXPECTED_NEW_WORDS <= NEW_GENERIC_ROLE_WORDS, (
    f"GENERIC_ROLE_WORDS ที่แก้แล้วขาดคำที่ควรมี: {EXPECTED_NEW_WORDS - NEW_GENERIC_ROLE_WORDS}"
)
print(f"ยืนยัน: GENERIC_ROLE_WORDS มีครบ {sorted(EXPECTED_NEW_WORDS)} แล้ว (รวมทั้งหมด {len(NEW_GENERIC_ROLE_WORDS)} คำ)")
print()


def calculate_skill_overlap_raw(resume_skills, job_skills):
    """จำลองพฤติกรรมเดิมก่อนแก้: ไม่ filter เลย ใช้ raw_skills ดิบตรงๆ"""
    resume_set = {s.lower() for s in resume_skills.get("hard_skills", []) + resume_skills.get("soft_skills", [])}
    job_set = {s.lower() for s in job_skills.get("hard_skills", []) + job_skills.get("soft_skills", [])}
    if not job_set:
        return None
    matched = resume_set & job_set
    return round(len(matched) / len(job_set), 3)


# ============================================================
# ขั้น 1-2: รัน extract_skills กับ JD ทุกอัน หา noise
# ============================================================
with open(os.path.join(REPO_ROOT, "synthetic_resumes", "job_descriptions.json"), encoding="utf-8") as f:
    JDS = json.load(f)

print("=" * 70)
print("ขั้น 1-2: extract_skills ของ JD ทุกอัน + noise ที่พบ")
print("=" * 70)
jd_raw_skills = {}
for jd_id, text in JDS.items():
    r = extract_skills(text)
    jd_raw_skills[jd_id] = r
    print(f"{jd_id}: hard={r['hard_skills']} soft={r['soft_skills']}")
print()
print(f"noise ที่ระบุด้วยมือ (เพิ่มเข้า GENERIC_ROLE_WORDS แล้วจริงใน test_full_pipeline_v4.py): {sorted(EXPECTED_NEW_WORDS)}")
print("  - 'Software Engineer' / 'Data Analyst' : ชื่อตำแหน่ง/role ไม่ใช่สกิล (เหมือน 'developer'/'engineer' ที่กรองอยู่แล้ว)")
print("  - 'Insight'  : คำทั่วไปจากวลี 'นำเสนอ Insight' ไม่ใช่ชื่อเครื่องมือ/ทักษะเฉพาะ")
print("  - 'HR'       : ตัวย่อแผนก ไม่ใช่สกิลเฉพาะ (ต่างจาก 'HRIS' ซึ่งเป็นชื่อระบบจริง)")
print("  - jd_marketing_manager ได้ hard=[] soft=[] (ดึงสกิลไม่ได้เลยสักคำ) — เป็นปัญหาคนละเรื่อง")
print("    (coverage ของ dictionary ไม่ใช่ noise) ไม่เกี่ยวกับ GENERIC_ROLE_WORDS จึงไม่รวมในการจำลองนี้")
print()

# ============================================================
# ขั้น 3: จับคู่เรซูเม่ -> JD ที่ตรงสายงานที่สุด (ตัดสินด้วยมือจาก field ใน manifest.csv)
# ============================================================
RESUME_TO_JD = {
    "01_it_junior_high_storytelling": "jd_backend_developer",
    "02_it_senior_keyword_heavy": "jd_senior_software_engineer",
    "03_it_data_analyst_medium": "jd_data_analyst",
    "04_accounting_entry_high_storytelling": "jd_accountant",
    "05_accounting_senior_keyword": "jd_accountant",
    "06_marketing_mid_high_storytelling": "jd_marketing_manager",
    "07_marketing_entry_short_edge_case": "jd_marketing_manager",
    "08_sales_mid_high_storytelling": "jd_sales_executive",
    "09_sales_entry_keyword": "jd_sales_executive",
    "10_customer_service_entry_short": None,   # ไม่มี JD ตรงสายใน job_descriptions.json
    "11_hr_mid_high_storytelling": "jd_hr_recruiter",
    "12_mech_engineer_senior_keyword": "jd_mechanical_engineer",
    "13_career_change_accounting_to_it": "jd_backend_developer",
    "14_career_change_teacher_to_hr": "jd_hr_recruiter",
    "15_it_very_long_senior": "jd_senior_software_engineer",
    "16_fresh_grad_almost_no_experience_edge_case": "jd_backend_developer",
    "17_graphic_design_mixed_thai_english": None,  # ไม่มี JD ตรงสาย
    "18_finance_analyst_high_storytelling": None,  # ไม่มี JD ตรงสาย
}

print("=" * 70)
print("ขั้น 3: เทียบพฤติกรรมเดิม (จำลอง) กับพฤติกรรมจริงหลังแก้ test_full_pipeline_v4.py")
print("=" * 70)

rows = []
pdf_files = sorted(glob.glob(os.path.join(REPO_ROOT, "synthetic_resumes", "pdf", "*.pdf")))
for pdf_path in pdf_files:
    resume_id = pdf_path.split("\\")[-1].replace(".pdf", "").replace("/", "")
    jd_id = RESUME_TO_JD.get(resume_id)
    if jd_id is None:
        print(f"{resume_id}: ข้าม (ไม่มี JD ตรงสายงานในชุดทดสอบ)")
        continue

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    extraction = pe.extract_text_from_pdf_bytes(pdf_bytes)
    resume_text = extraction["text"]

    raw_resume_skills = extract_skills(resume_text)
    raw_job_skills = jd_raw_skills[jd_id]

    # "old": จำลองพฤติกรรมเดิมก่อนแก้ (ไม่ filter เลย)
    old_ratio = calculate_skill_overlap_raw(raw_resume_skills, raw_job_skills)
    old_penalty = get_skill_penalty(old_ratio)

    # "new": เรียก filter_generic_skills + calculate_skill_overlap ตัวจริงจาก test_full_pipeline_v4.py
    # ที่แก้แล้ว (ใช้ GENERIC_ROLE_WORDS ของโมดูลเองภายใน ไม่ต้องส่ง word set เข้าไป)
    clean_resume_skills = filter_generic_skills(raw_resume_skills)
    clean_job_skills = filter_generic_skills(raw_job_skills)

    new_ratio = calculate_skill_overlap(clean_resume_skills, clean_job_skills)
    new_penalty = get_skill_penalty(new_ratio)

    changed = (old_ratio != new_ratio) or (old_penalty != new_penalty)
    rows.append({
        "resume": resume_id,
        "jd": jd_id,
        "old_ratio": old_ratio,
        "new_ratio": new_ratio,
        "old_penalty": old_penalty,
        "new_penalty": new_penalty,
        "changed": changed,
    })

print()
print(f"{'resume':<48} {'jd':<26} {'old_ratio':>9} {'new_ratio':>9} {'old_pen':>8} {'new_pen':>8}  changed")
for row in rows:
    print(f"{row['resume']:<48} {row['jd']:<26} {str(row['old_ratio']):>9} {str(row['new_ratio']):>9} "
          f"{row['old_penalty']:>8} {row['new_penalty']:>8}  {row['changed']}")

changed_rows = [r for r in rows if r["changed"]]
print()
print(f"สรุป: ทดสอบ {len(rows)} ไฟล์ (มี JD ให้จับคู่) — เปลี่ยน {len(changed_rows)} ไฟล์")

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_noise_analysis.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
print(f"บันทึกผลลัพธ์ไว้ที่ {output_path}")
