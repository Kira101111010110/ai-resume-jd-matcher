"""
รวมผล OpenAI ที่ทดสอบใหม่ (gpt-5.6-luna) เข้ากับไฟล์ comparison_results.csv เดิม
โดยแทนที่เฉพาะแถวที่ provider == "openai" ด้วยผลใหม่ ส่วน gemini/claude คงเดิมไว้ไม่แตะ

วิธีใช้:
    1. รัน research/run_comparison_openai_retest.py ก่อน
       จะได้ไฟล์ comparison_results_openai_retest.csv
    2. รัน: python research/merge_openai_retest.py
    3. ได้ไฟล์ comparison_results_merged.csv ที่รวมผลล่าสุดครบทั้ง 3 provider
"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # CSV ทั้งหมดอยู่ใน research/
OLD_CSV = BASE_DIR / "comparison_results.csv"                    # ผลเดิม (gemini/openai เก่า/claude)
NEW_OPENAI_CSV = BASE_DIR / "comparison_results_openai_retest.csv"  # ผล openai รอบใหม่ (gpt-5.6-luna)
MERGED_CSV = BASE_DIR / "comparison_results_merged.csv"


def main():
    old_df = pd.read_csv(OLD_CSV)
    new_openai_df = pd.read_csv(NEW_OPENAI_CSV)

    before_count = len(old_df[old_df["provider"] == "openai"])
    after_count = len(new_openai_df)

    # ตัดแถว openai เก่าออก แล้วเอาแถว openai ใหม่มาต่อแทน
    kept_df = old_df[old_df["provider"] != "openai"].copy()
    merged_df = pd.concat([kept_df, new_openai_df], ignore_index=True)

    # เรียงกลับให้เหมือนโครงสร้างเดิม (resume_id, job_id, provider) เพื่อให้อ่านง่าย
    merged_df = merged_df.sort_values(["resume_id", "job_id", "provider"]).reset_index(drop=True)

    merged_df.to_csv(MERGED_CSV, index=False, encoding="utf-8-sig")

    print(f"แถว openai เดิม (gpt-4o-mini): {before_count}")
    print(f"แถว openai ใหม่ (gpt-5.6-luna): {after_count}")
    print(f"รวมทั้งหมดหลัง merge: {len(merged_df)} แถว")
    print(f"บันทึกที่: {MERGED_CSV}")


if __name__ == "__main__":
    main()
