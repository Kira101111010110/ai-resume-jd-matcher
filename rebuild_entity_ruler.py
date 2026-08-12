"""
rebuild_entity_ruler.py
========================
สร้าง skill-extractor-model ใหม่จาก cleaned_patterns.jsonl (hard + soft skills)

**ไม่ใช่การเทรน ML** — EntityRuler เป็น rule-based (pattern matching)
ไม่มี gradient descent, ไม่ต้องใช้ GPU, ไม่ต้องมี validation set
รันไม่กี่วินาทีก็เสร็จ ต่างจาก SBERT fine-tune ที่ต้องเทรนจริงบน GPU

วิธีใช้:
    python rebuild_entity_ruler.py \
        --hard-patterns cleaned_hard.jsonl \
        --soft-patterns cleaned_soft.jsonl \
        --output ./skill-extractor-model \
        --base-model en_core_web_lg

หลังรันเสร็จ:
    1. เอาโฟลเดอร์ output ไปแทนที่ skill-extractor-model เดิม
    2. restart uvicorn (สำคัญ! ไม่งั้น app.py ที่รันอยู่จะยังใช้โมเดลเก่าในหน่วยความจำ)
    3. ทดสอบผ่าน batch_test_pipeline.py หรือ call_api.py ว่า noise word หายจริง
"""

import argparse
import json
import spacy
from pathlib import Path


def load_patterns(path: str):
    """อ่าน jsonl ที่มาจาก clean_skill_dictionary.py"""
    patterns = []
    if not path:
        return patterns
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                patterns.append(json.loads(line))
    return patterns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hard-patterns", help="cleaned_patterns.jsonl (label=HARD_SKILL)")
    parser.add_argument("--soft-patterns", help="cleaned_patterns.jsonl (label=SOFT_SKILL)")
    parser.add_argument("--output", default="./skill-extractor-model")
    parser.add_argument("--base-model", default="en_core_web_lg",
                         help="base spaCy model เดิมที่ใช้ตอนแรก")
    args = parser.parse_args()

    if not args.hard_patterns and not args.soft_patterns:
        raise SystemExit("ต้องระบุอย่างน้อย --hard-patterns หรือ --soft-patterns")

    print(f"โหลด base model: {args.base_model} ...")
    nlp = spacy.load(args.base_model)

    # ลบ entity_ruler เก่าถ้ามีอยู่แล้ว (กันซ้อน pattern เก่า)
    if "entity_ruler" in nlp.pipe_names:
        nlp.remove_pipe("entity_ruler")

    # overwrite_ents=True สำคัญมาก: base model (en_core_web_lg/sm) มี NER ติดมา
    # อยู่แล้ว ที่มักจับคำแบบ "Python"->GPE, "Kubernetes"->ORG ผิดๆ ถ้าไม่ตั้งค่านี้
    # entity_ruler จะ "ข้าม" ไม่ tag HARD_SKILL ทับ เพราะเข้าใจว่า span ถูกจับไปแล้ว
    # (บั๊กนี้เจอจริงตอนทดสอบ: Python/Kubernetes/Apache Spark หายไปจาก output เงียบๆ)
    ruler = nlp.add_pipe(
        "entity_ruler",
        config={"phrase_matcher_attr": "LOWER", "overwrite_ents": True},
    )

    all_patterns = load_patterns(args.hard_patterns) + load_patterns(args.soft_patterns)

    # กันเผื่อ pattern format ผิด (ต้องมี label กับ pattern เท่านั้น)
    valid_patterns = [
        p for p in all_patterns
        if isinstance(p, dict) and "label" in p and "pattern" in p
    ]
    skipped = len(all_patterns) - len(valid_patterns)

    ruler.add_patterns(valid_patterns)

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(output_path)

    print(f"\nสร้างเสร็จแล้ว: {output_path.resolve()}")
    print(f"จำนวน pattern ทั้งหมดที่ใส่เข้าไป: {len(valid_patterns)}")
    if skipped:
        print(f"⚠️ ข้าม {skipped} pattern ที่ format ไม่ถูกต้อง")

    # ทดสอบเร็วๆ ว่าโหลดกลับมาใช้ได้จริง + ลอง sanity check กับ noise word เก่า
    print("\n--- ทดสอบโหลดโมเดลที่เพิ่งสร้าง ---")
    test_nlp = spacy.load(output_path)
    sample_text = (
        "Backend Developer with experience in Python, Kubernetes, and Apache Spark. "
        "Progress on the final project included strong communication and Management skills. "
        "ENGINEERING background with Email support duties."
    )
    doc = test_nlp(sample_text)
    hard = sorted(set(e.text for e in doc.ents if e.label_ == "HARD_SKILL"))
    soft = sorted(set(e.text for e in doc.ents if e.label_ == "SOFT_SKILL"))
    print(f"Hard skills ที่ดึงได้: {hard}")
    print(f"Soft skills ที่ดึงได้: {soft}")
    print("\n(เช็คว่า Backend, Developer, Progress, Management, ENGINEERING, Email")
    print(" ไม่โผล่มาใน list ข้างบน ถ้าไม่มี = สำเร็จ)")


if __name__ == "__main__":
    main()
