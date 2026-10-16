# -*- coding: utf-8 -*-
"""
ทดสอบการตรวจจับ/ดึงสกิลจากกราฟิกใน pdf_extraction.py กับไฟล์ PDF ในเครื่อง
วิธีรัน (รันจากไดเรกทอรีไหนก็ได้): python local_manual_scripts/test_visual_skills.py path/to/resume.pdf

พิมพ์: หน้าที่ตรวจเจอ + เหตุผล, ตัวเลขดิบของแต่ละหน้า (area ratio ของรูป, จำนวน rect/curve)
       เพื่อเอาไปจูน threshold, visual_skills, method, warning และ 15 บรรทัดสุดท้ายของ text
"""

import os
import sys
import io
import pdfplumber

# เพิ่ม root ของ repo เข้า sys.path เพราะไฟล์นี้อยู่ใน local_manual_scripts/ ไม่ใช่ root
# ทำให้ import pdf_extraction ได้ไม่ว่าจะรันจาก working directory ไหน
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pdf_extraction as pe


def main():
    if len(sys.argv) != 2:
        print("วิธีรัน: python local_manual_scripts/test_visual_skills.py path/to/resume.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"=== ไฟล์: {pdf_path} ===\n")

    # --- ตัวเลขดิบของทุกหน้า (ไว้จูน threshold) ---
    print("--- ตัวเลขดิบต่อหน้า (สำหรับจูน threshold) ---")
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            stats = pe._analyze_page_visuals(page)
            ratios_str = ", ".join(f"{r:.4f}" for r in stats["image_ratios"]) or "-"
            print(f"หน้า {i + 1}:")
            print(f"  image area ratios (เทียบพื้นที่หน้า): [{ratios_str}]")
            print(f"  small_image_count (<= {pe.MAX_ICON_IMAGE_AREA_RATIO}): {stats['small_image_count']}")
            print(f"  total_rect_count: {stats['total_rect_count']}, candidate_rect_count (ขนาดเข้าเงื่อนไข skill bar): {stats['candidate_rect_count']}")
            print(f"  max_rect_group_size (แถบความสูงเท่ากันกลุ่มใหญ่สุด): {stats['max_rect_group_size']}")
            print(f"  curve_count: {stats['curve_count']}")
    print()

    # --- ผลการตรวจจับหน้าที่น่าจะมีกราฟิกสกิล ---
    visual_pages = pe._detect_visual_pages(pdf_bytes)
    print("--- หน้าที่ตรวจพบว่ามีกราฟิกสกิล ---")
    if visual_pages:
        for idx, reason in visual_pages:
            print(f"  หน้า {idx + 1}: {reason}")
    else:
        print("  ไม่พบหน้าที่มีกราฟิกสกิล")
    print()

    # --- เรียก extract_text_from_pdf_bytes เต็มๆ (รวมเรียก Gemini vision ถ้าตรวจพบ) ---
    result = pe.extract_text_from_pdf_bytes(pdf_bytes)

    print("--- ผลจาก extract_text_from_pdf_bytes ---")
    print(f"method: {result['method']}")
    print(f"warning: {result['warning']}")
    print(f"visual_detection_reason: {result['visual_detection_reason']}")
    print(f"visual_skills_used: {result['visual_skills_used']}")
    print(f"visual_skills: {result['visual_skills']}")
    print()

    print("--- 15 บรรทัดสุดท้ายของ text ---")
    lines = result["text"].splitlines()
    for line in lines[-15:]:
        print(line)


if __name__ == "__main__":
    main()
