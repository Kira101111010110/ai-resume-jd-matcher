# -*- coding: utf-8 -*-
"""
สร้าง PDF ทดสอบ 3 ไฟล์สำหรับทดสอบการตรวจจับ/ดึงสกิลจากกราฟิกใน pdf_extraction.py
ใช้ PyMuPDF (fitz) วาดข้อความ/กราฟิกตรงลงหน้า PDF และ Pillow สร้างรูป raster (ไอคอน/badge)
ไม่ใช้ reportlab เพราะ generate_synthetic_resumes.py เดิมพึ่งฟอนต์ไทยที่ไม่มีในเครื่องนี้
เนื้อหาเป็นภาษาอังกฤษล้วนเพื่อเลี่ยงปัญหาฟอนต์ — จุดสนใจของไฟล์พวกนี้คือกราฟิก ไม่ใช่เนื้อหาภาษาไทย

Output: synthetic_resumes/visual/{A,B,C}.pdf
รันจากไดเรกทอรีไหนก็ได้ (path ของ output ผูกกับตำแหน่งไฟล์นี้ ไม่ใช่ working directory)
"""

import os
import io
import fitz
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "synthetic_resumes", "visual")
PAGE_W, PAGE_H = 595, 842  # A4 เป็น point (72 dpi)


def _icon_png(color=(70, 130, 180), size=14) -> bytes:
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, size - 1, size - 1], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _photo_png(size=(90, 120)) -> bytes:
    img = Image.new("RGB", size, (210, 190, 170))
    draw = ImageDraw.Draw(img)
    draw.ellipse([15, 15, size[0] - 15, size[1] - 40], fill=(230, 205, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _badge_png(text: str, size=(230, 68), bg=(40, 44, 52), fg=(255, 255, 255)) -> bytes:
    """badge raster ที่เขียนชื่อสกิลเป็น "พิกเซล" ไม่ใช่ข้อความที่เลือกได้ — จำลองโลโก้/ไอคอนสกิลในเรซูเม่จริง
    วาดที่ความละเอียดสูงกว่าขนาดที่จะวางลงหน้า PDF (ดู badge_w/badge_h ใน make_file_c) เพื่อให้ตัวอักษรยังชัดอยู่
    หลัง render หน้าทั้งหน้าเป็นภาพส่งให้ Gemini (ขนาดบนหน้า PDF ต้องเล็ก ไม่งั้นจะไม่เข้าเงื่อนไข MAX_ICON_IMAGE_AREA_RATIO)"""
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0] - w) / 2 - bbox[0], (size[1] - h) / 2 - bbox[1]), text, font=font, fill=fg)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _insert_lines(page, lines, x=50, y=60, size=11, gap=16, bold=False):
    font = "hebo" if bold else "helv"
    for line in lines:
        page.insert_text((x, y), line, fontsize=size, fontname=font)
        y += gap
    return y


def make_file_a(path):
    """A: resume ปกติ + รูปโปรไฟล์ 1 รูป + ไอคอนติดต่อเล็กๆ 4 อัน (โทรศัพท์/อีเมล/ที่อยู่/LinkedIn)
    ไม่มีกราฟิกสกิลเลย — ใช้ทดสอบว่า "ไม่ควร" trigger (แต่ไอคอนติดต่อ 4 อันอาจจะ trigger กฎ small-image ก็ได้
    ซึ่งเป็นเคสที่ตั้งใจทดสอบไว้ตามที่ผู้ใช้ขอ ไม่ได้ถือว่าเป็นบั๊กของไฟล์นี้)"""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    page.insert_image(fitz.Rect(450, 40, 450 + 90, 40 + 120), stream=_photo_png())

    y = _insert_lines(page, ["John Carter", "Product Manager"], y=60, size=18, gap=24, bold=True)
    y += 10

    contact_items = [
        "Phone: 08x-xxx-xxxx",
        "Email: john.carter@example.com",
        "Address: Bangkok, Thailand",
        "LinkedIn: linkedin.com/in/johncarter",
    ]
    icon_x, icon_size = 50, 14
    for i, line in enumerate(contact_items):
        iy = y + i * 18
        page.insert_image(fitz.Rect(icon_x, iy, icon_x + icon_size, iy + icon_size), stream=_icon_png())
        page.insert_text((icon_x + icon_size + 6, iy + icon_size - 3), line, fontsize=10, fontname="helv")
    y += len(contact_items) * 18 + 20

    summary = (
        "John Carter is a product manager with six years of experience leading cross-functional "
        "teams to ship consumer mobile applications used by millions of users across Southeast Asia, "
        "focusing on user research, roadmap planning, and close collaboration with engineering and design."
    )
    y = _insert_lines(page, ["Summary"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(summary, 85), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Experience"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(
        "Senior Product Manager, Globex Inc (2021 - Present): led the launch of a new onboarding "
        "flow that increased activation rate by 22 percent within the first quarter after release.",
        85
    ), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Skills"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(
        "Product Strategy, Agile, Stakeholder Management, Jira, Figma for wireframing, basic SQL for reporting",
        85
    ), y=y, size=10.5, gap=14)

    doc.save(path)
    doc.close()


def make_file_b(path):
    """B: resume ปกติ + skill bar (rect) ที่มีชื่อสกิลเป็น "ข้อความจริง" อยู่แล้ว
    คาดหวัง: อาจ trigger (มีแถบความสูงเท่ากันหลายแถบ) แต่ visual_skills ควรว่าง/น้อย เพราะ dedupe ตัดชื่อที่มีใน text ออก"""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    y = _insert_lines(page, ["Alice Wong", "Backend Engineer"], y=60, size=18, gap=24, bold=True)
    y += 10

    summary = (
        "Alice Wong is a backend engineer with four years of experience building scalable APIs and "
        "data pipelines for e-commerce platforms, with a strong focus on performance and reliability."
    )
    y = _insert_lines(page, ["Summary"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(summary, 85), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Experience"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(
        "Backend Engineer, Initech (2021 - Present): redesigned the order processing service, "
        "cutting average response time from 1.2 seconds to 300 milliseconds.",
        85
    ), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Skills"], y=y, size=13, gap=18, bold=True)
    y += 6

    bar_h = 10
    track_w = 220
    skill_levels = [("Python", 0.9), ("JavaScript", 0.7), ("SQL", 0.8), ("Docker", 0.6), ("Kubernetes", 0.5)]
    for name, level in skill_levels:
        page.insert_text((50, y + bar_h - 1), name, fontsize=10.5, fontname="helv")
        bar_x = 180
        # ใช้ Shape API ตรงๆ แทน page.draw_rect เพราะ draw_rect แทรก "h" (closepath) ซ้ำ
        # ท้ายพาธ ทำให้ pdfplumber จัดเป็น "curve" ไม่ใช่ "rect" (ตรวจสอบแล้วด้วย pdfplumber.open())
        # closePath=False ทำให้ได้พาธสี่เหลี่ยมล้วนๆ ตรงกับที่ skill bar จริงบน Canva/Word มักสร้างออกมา
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(bar_x, y, bar_x + track_w, y + bar_h))
        shape.finish(color=None, fill=(0.85, 0.85, 0.85), closePath=False)
        shape.commit()

        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(bar_x, y, bar_x + track_w * level, y + bar_h))
        shape.finish(color=None, fill=(0.2, 0.4, 0.8), closePath=False)
        shape.commit()
        y += bar_h + 10

    doc.save(path)
    doc.close()


def make_file_c(path):
    """C: resume ปกติ + สกิล "Docker", "Figma", "PostgreSQL" เป็นภาพ raster badge เท่านั้น
    (ไม่มีชื่อ 3 สกิลนี้ในข้อความที่เลือกได้เลย) — คาดหวัง: trigger และได้ 3 สกิลนี้กลับมาจาก visual_skills"""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    y = _insert_lines(page, ["Maria Santos", "Full-stack Developer"], y=60, size=18, gap=24, bold=True)
    y += 10

    summary = (
        "Maria Santos is a full-stack developer with five years of experience building web "
        "applications end to end, from database design to responsive front-end interfaces, "
        "collaborating closely with product and design teams."
    )
    y = _insert_lines(page, ["Summary"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(summary, 85), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Experience"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap(
        "Full-stack Developer, Soylent Corp (2020 - Present): built an internal analytics tool "
        "adopted by every department, reducing manual reporting work by eight hours per week.",
        85
    ), y=y, size=10.5, gap=14)
    y += 10

    y = _insert_lines(page, ["Skills"], y=y, size=13, gap=18, bold=True)
    y = _insert_lines(page, _wrap("HTML, CSS, JavaScript, React", 85), y=y, size=10.5, gap=14)
    y += 16

    y = _insert_lines(page, ["Tools"], y=y, size=13, gap=18, bold=True)
    y += 6
    # ขนาดบนหน้า PDF ต้องเล็กพอจะถือเป็น "ไอคอน" (ratio <= MAX_ICON_IMAGE_AREA_RATIO = 0.01 บนหน้า A4)
    # 115x34pt ~= 3910 pt^2 / พื้นที่หน้า A4 501070 pt^2 = ratio ~0.0078
    badge_w, badge_h, gap_x = 115, 34, 15
    badge_x = 50
    for name in ["Docker", "Figma", "PostgreSQL"]:
        page.insert_image(
            fitz.Rect(badge_x, y, badge_x + badge_w, y + badge_h),
            stream=_badge_png(name)
        )
        badge_x += badge_w + gap_x

    doc.save(path)
    doc.close()


def _wrap(text, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    make_file_a(os.path.join(OUT_DIR, "A.pdf"))
    make_file_b(os.path.join(OUT_DIR, "B.pdf"))
    make_file_c(os.path.join(OUT_DIR, "C.pdf"))
    print(f"สร้างไฟล์ทดสอบแล้วใน {OUT_DIR}: A.pdf, B.pdf, C.pdf")


if __name__ == "__main__":
    main()
