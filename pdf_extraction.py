"""
ดาวน์โหลด PDF จาก URL (เช่น Cloudinary/Supabase secure_url) แล้วสกัดข้อความ
กลยุทธ์: ใช้ pdfplumber ก่อนเสมอ (เร็ว, layout=True ช่วยจัดการ resume หลายคอลัมน์)
แล้วเช็คว่าผลลัพธ์ "น่าสงสัยว่าเพี้ยน/ไม่พอ" ไหม จาก 2 สัญญาณ:
  1. สัดส่วน null byte / control character สูงผิดปกติ (ปัญหาฟอนต์ฝังใน PDF)
  2. จำนวนคำที่สกัดได้น้อยเกินไป (pdfplumber ดึง text layer ไม่ได้ หรือ layout ซับซ้อนเกิน)
ถ้าเข้าเงื่อนไขใดเงื่อนไขหนึ่ง ค่อย fallback ไปใช้ OCR (Tesseract) ซึ่งช้ากว่ามากแต่ทนทานกว่า
ไม่รัน OCR คู่กับ pdfplumber ทุกไฟล์ เพราะจะทำให้ request ทุกอันช้าลงโดยไม่จำเป็น
"""

import io
import os
import re
import requests
import pdfplumber
import fitz  # PyMuPDF — ใช้ render หน้า PDF เป็นรูปภาพสำหรับ OCR และสำหรับส่งให้ Gemini vision อ่านกราฟิกสกิล
import pytesseract
from PIL import Image

# สัดส่วนอักขระผิดปกติ (null byte / control char) ที่ยอมรับได้ก่อนจะถือว่า "น่าสงสัยว่าเพี้ยน"
SUSPICIOUS_CHAR_THRESHOLD = 0.001  # เกิน 0.1% ของความยาวข้อความทั้งหมด ถือว่าน่าสงสัย
MIN_WORD_COUNT = 30                # ต่ำกว่านี้ ถือว่าสกัดได้ไม่พอ (resume จริงควรมีคำมากกว่านี้มาก)

# ============================================================
# ตรวจจับ "กราฟิกสกิล" ในหน้า PDF (skill bar / กราฟวงกลม % / ดาว rating / ไอคอน-โลโก้)
# เพื่อส่งหน้านั้นให้ Gemini vision อ่านสกิลที่อยู่ในรูปแทนข้อความ (pdfplumber/OCR อ่านรูปไม่ได้)
# ============================================================
VISUAL_SKILL_EXTRACTION_ENV = "VISUAL_SKILL_EXTRACTION"  # ตั้งเป็น "false" เพื่อปิดฟีเจอร์นี้

# รูปที่มีพื้นที่ไม่เกินนี้ (เทียบกับพื้นที่หน้าทั้งหมด) ถือว่าเป็น "ไอคอน/โลโก้" ไม่ใช่รูปโปรไฟล์
# รูปโปรไฟล์ขนาด ~3x4ซม. บน A4 กินพื้นที่ประมาณ 2% ของหน้า จึงต้องตั้งค่านี้ให้ต่ำกว่านั้นชัดเจน
MAX_ICON_IMAGE_AREA_RATIO = 0.01
# ต้องเจอ "ไอคอนเล็ก" ตั้งแต่จำนวนนี้ขึ้นไปในหน้าเดียว ถึงจะถือว่าน่าจะเป็นไอคอนสกิล/โลโก้เทคโนโลยี
# (เรซูเม่ไทยเกือบทุกใบมีรูปโปรไฟล์ 1 รูป แต่รูปโปรไฟล์ถูกกรองออกไปแล้วด้วย MAX_ICON_IMAGE_AREA_RATIO ด้านบน
#  — threshold นี้กันกรณีไอคอนติดต่อ (โทรศัพท์/อีเมล) 1-2 อันข้างข้อมูลติดต่อ ซึ่งเป็นของตกแต่งปกติ ไม่ใช่สกิล)
MIN_SMALL_IMAGES_FOR_VISUAL = 3

# แถบกราฟ (skill bar) ต้องสูงอยู่ในช่วงนี้ — สูงกว่านี้มักเป็นกรอบ/แถบพื้นหลังตกแต่ง ไม่ใช่แถบวัดระดับสกิล
# เตี้ยกว่านี้มักเป็นเส้นคั่นบางๆ ระหว่าง section ไม่ใช่แถบวัดระดับ
MIN_RECT_HEIGHT_FOR_SKILL_BAR = 3
MAX_RECT_HEIGHT_FOR_SKILL_BAR = 20
MIN_RECT_WIDTH_FOR_SKILL_BAR = 15     # กันเส้นคั่นแนวตั้งบางๆ ที่กว้างไม่พอจะเป็นแถบ
SKILL_BAR_HEIGHT_TOLERANCE = 2.0      # ความสูงต่างกันไม่เกินนี้ (pt) ถือว่า "เท่ากัน" (กันความเพี้ยนเล็กน้อย)
MIN_SKILL_BAR_RECTS = 4               # ต้องมีแถบความสูงเท่ากันอย่างน้อยเท่านี้ ถึงจะถือเป็นกลุ่ม skill bar จริง

MIN_CURVES_FOR_CHART = 8   # จำนวน curve ขั้นต่ำในหน้าเดียว ถึงจะถือว่าน่าจะเป็นกราฟวงกลม % หรือดาว/จุด rating
MAX_VISUAL_PAGES_TO_RENDER = 2   # render ส่งให้ Gemini vision ไม่เกินนี้ กันค่าใช้จ่าย/เวลาที่เพิ่มขึ้นถ้าเรซูเม่มีหลายหน้า


def _suspicious_char_ratio(text: str) -> float:
    if not text:
        return 1.0
    suspicious = len(re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', text))
    return suspicious / len(text)


def _clean_extracted_text(text: str) -> str:
    """ลบ bullet point ขยะ/ช่องว่างซ้ำที่ไม่ช่วยอะไร แต่ไม่ลบ control character ทิ้ง
    เพราะยังต้องใช้ค่านั้นคำนวณ _suspicious_char_ratio ก่อน"""
    if not text:
        return ""
    text = re.sub(r'[•‣◦⁃∙]', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    pages_text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            # layout=True ช่วยรักษาลำดับคอลัมน์ของ resume ที่มีหลายคอลัมน์
            t = page.extract_text(layout=True, x_tolerance=2, y_tolerance=3)
            if t:
                pages_text.append(t)
    return "\n".join(pages_text).strip()


def _extract_with_ocr(pdf_bytes: bytes, lang: str = "tha+eng") -> str:
    """
    Fallback: render แต่ละหน้าเป็นรูปภาพด้วย PyMuPDF แล้วอ่านด้วย Tesseract OCR
    ช้ากว่า pdfplumber มาก (หลักวินาทีต่อหน้า) เรียกใช้เฉพาะตอนจำเป็นเท่านั้น
    ต้องติดตั้ง Tesseract OCR ในเครื่อง + language pack "tha" ก่อนใช้งานได้จริง
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    ocr_pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_pages.append(pytesseract.image_to_string(img, lang=lang))
    return "\n".join(ocr_pages).strip()


def _needs_ocr(text: str) -> tuple[bool, str]:
    """คืนค่า (ต้องใช้ OCR ไหม, เหตุผล) จาก 2 สัญญาณรวมกัน"""
    if not text:
        return True, "ไม่มีข้อความเลย"

    ratio = _suspicious_char_ratio(text)
    if ratio > SUSPICIOUS_CHAR_THRESHOLD:
        return True, f"พบอักขระผิดปกติ {ratio:.2%} (อาจมาจากปัญหาฟอนต์ใน PDF)"

    word_count = len(text.split())
    if word_count < MIN_WORD_COUNT:
        return True, f"สกัดได้แค่ {word_count} คำ (น้อยเกินกว่าจะเป็น resume ปกติ)"

    return False, ""


def _visual_extraction_enabled() -> bool:
    return os.environ.get(VISUAL_SKILL_EXTRACTION_ENV, "true").strip().lower() not in ("0", "false", "no")


def _analyze_page_visuals(page) -> dict:
    """
    วิเคราะห์ตัวเลขดิบของหน้า PDF หนึ่งหน้า (ไม่ตัดสินใจ trigger ตรงนี้) แยกออกมาจาก
    _detect_visual_pages เพื่อให้ test script เรียกดูตัวเลขดิบได้ ใช้จูน threshold กับเรซูเม่จริง
    """
    page_area = (page.width * page.height) or 1.0
    image_ratios = [
        (img["width"] * img["height"]) / page_area for img in page.images
    ]
    small_image_count = sum(1 for r in image_ratios if r <= MAX_ICON_IMAGE_AREA_RATIO)

    candidate_rects = [
        r for r in page.rects
        if MIN_RECT_HEIGHT_FOR_SKILL_BAR <= r["height"] <= MAX_RECT_HEIGHT_FOR_SKILL_BAR
        and r["width"] >= MIN_RECT_WIDTH_FOR_SKILL_BAR
    ]
    # จัดกลุ่มแถบที่ความสูงใกล้เคียงกัน (ภายใน tolerance) แล้วหากลุ่มที่ใหญ่ที่สุด
    # เพราะ skill bar ของจริงมักมีหลายแถบความสูงเท่ากันเรียงกัน ไม่ใช่แถบเดี่ยวๆ
    height_groups = []
    for r in sorted(candidate_rects, key=lambda r: r["height"]):
        h = r["height"]
        for g in height_groups:
            if abs(g[0] - h) <= SKILL_BAR_HEIGHT_TOLERANCE:
                g.append(h)
                break
        else:
            height_groups.append([h])
    max_rect_group_size = max((len(g) for g in height_groups), default=0)

    return {
        "image_ratios": image_ratios,
        "small_image_count": small_image_count,
        "total_rect_count": len(page.rects),
        "candidate_rect_count": len(candidate_rects),
        "max_rect_group_size": max_rect_group_size,
        "curve_count": len(page.curves),
    }


def _detect_visual_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """
    คืนลิสต์ (page_index, เหตุผล) ของหน้าที่น่าจะมีกราฟิกสกิล (skill bar / กราฟวงกลม % / ดาว rating / ไอคอน-โลโก้)
    page_index เริ่มที่ 0 ตามลำดับเดียวกับที่ fitz ใช้ตอน render (ดู _render_pages_as_png)
    """
    results = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            stats = _analyze_page_visuals(page)
            reasons = []
            if stats["small_image_count"] >= MIN_SMALL_IMAGES_FOR_VISUAL:
                reasons.append(f"พบไอคอน/โลโก้ขนาดเล็ก {stats['small_image_count']} รูป")
            if stats["max_rect_group_size"] >= MIN_SKILL_BAR_RECTS:
                reasons.append(f"พบแถบกราฟิกความสูงเท่ากัน {stats['max_rect_group_size']} แถบ (น่าจะเป็น skill bar)")
            if stats["curve_count"] >= MIN_CURVES_FOR_CHART:
                reasons.append(f"พบเส้นโค้งจำนวนมาก {stats['curve_count']} เส้น (น่าจะเป็นกราฟวงกลม %/ดาว rating)")
            if reasons:
                results.append((i, "; ".join(reasons)))
    return results


def _render_pages_as_png(pdf_bytes: bytes, page_indexes: list[int], dpi: int = 150) -> list[bytes]:
    """render หน้า PDF ที่ระบุเป็นภาพ PNG (bytes) เพื่อส่งให้ Gemini vision อ่าน
    จำกัดไม่เกิน MAX_VISUAL_PAGES_TO_RENDER หน้า กันกรณีผู้เรียกส่ง page_indexes มาเกิน"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for i in page_indexes[:MAX_VISUAL_PAGES_TO_RENDER]:
        pix = doc[i].get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))
    return images


_SKILL_BOUNDARY_CHARS = r"A-Za-z0-9+#."


def _is_skill_in_text(skill: str, text: str) -> bool:
    """เช็คว่าสกิลนี้มีอยู่ใน text แล้วหรือยัง (case-insensitive)
    ใช้ negative lookaround แทน \\b ธรรมดา เพราะชื่อสกิลสั้นๆ อย่าง "C"/"R"/"Go"
    ต้องไม่ไปจับคำย่อยใน "Computer"/"Research"/"Google" และสกิลที่มีสัญลักษณ์อย่าง "C++"/"C#"
    ใช้ \\b ธรรมดาไม่ได้ผลเพราะ +/# ไม่ใช่ word character"""
    pattern = (
        r"(?<![" + _SKILL_BOUNDARY_CHARS + r"])"
        + re.escape(skill)
        + r"(?![" + _SKILL_BOUNDARY_CHARS + r"])"
    )
    return re.search(pattern, text, re.IGNORECASE) is not None


def _append_warning(existing: str | None, new_msg: str) -> str:
    """ต่อท้าย warning ข้อความใหม่ โดยไม่เขียนทับของเดิมถ้ามีอยู่แล้ว"""
    return f"{existing} | {new_msg}" if existing else new_msg


def _append_visual_skills(text: str, pdf_bytes: bytes, visual_pages: list[tuple[int, str]]) -> tuple[str, list[str]]:
    """
    เรียก Gemini vision อ่านสกิลจากกราฟิกในหน้าที่ตรวจพบ แล้วต่อท้าย text เฉพาะสกิลที่ยังไม่มีอยู่แล้ว
    คืนค่า (text ใหม่, รายการสกิลใหม่ที่ต่อท้ายจริง)
    โยน exception ออกไปให้ผู้เรียก catch — ผู้เรียกต้อง fallback กลับไปใช้ text เดิมถ้าขั้นนี้ล้มเหลว
    """
    from llm_providers import extract_visual_skills  # import ในฟังก์ชัน กันปัญหา circular import ตอนโหลดโมดูล

    page_indexes = [p for p, _ in visual_pages][:MAX_VISUAL_PAGES_TO_RENDER]
    images = _render_pages_as_png(pdf_bytes, page_indexes)
    skills = extract_visual_skills(images)

    new_skills = [s for s in skills if not _is_skill_in_text(s, text)]
    if new_skills:
        text = text + "\nSkills (from graphics): " + ", ".join(new_skills)
    return text, new_skills


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> dict:
    """
    สกัดข้อความจาก pdf_bytes พร้อมข้อมูลว่าใช้วิธีไหน แล้วถ้าตรวจพบว่าหน้าไหนมีกราฟิกสกิล
    ก็เรียก Gemini vision อ่านสกิลจากกราฟิกมาต่อท้าย text ให้อัตโนมัติ (ควบคุมเปิด/ปิดด้วย env
    VISUAL_SKILL_EXTRACTION) เพื่อให้ SBERT/spaCy/skill_overlap_ratio เห็นสกิลที่เป็นรูปด้วย
    คืนค่า dict: {
        "text": str,
        "method": "text_layer" | "ocr_fallback",
        "warning": str | None,                   # ไม่ None ถ้าข้อความ/กราฟิกอาจยังเพี้ยนหรือดึงไม่ได้บางส่วน
        "visual_skills": list[str],               # สกิลใหม่จากกราฟิกที่ต่อท้าย text จริง (ไม่รวมที่ dedupe ออกไป)
        "visual_skills_used": bool,                # True ถ้ามีสกิลใหม่จากกราฟิกถูกต่อท้ายจริง
        "visual_detection_reason": str | None,     # เหตุผลที่ตรวจพบหน้ากราฟิก (None ถ้าไม่พบเลยทั้งเล่ม)
    }
    โยน exception ออกไปถ้าสกัดข้อความไม่ได้เลยทั้ง 2 วิธี (เหมือนเดิม — ไม่เกี่ยวกับขั้นดึงกราฟิก)
    """
    raw_text = _extract_with_pdfplumber(pdf_bytes)
    text = _clean_extracted_text(raw_text)

    needs_ocr, reason = _needs_ocr(raw_text)  # เช็คจากข้อความก่อน clean เพื่อนับ control char ได้ถูกต้อง

    if not needs_ocr:
        # กรณีปกติ: pdfplumber ให้ผลดีพอ ไม่ต้องเสียเวลารัน OCR เพิ่ม
        method, warning = "text_layer", None
    else:
        # กรณีน่าสงสัย — ลอง OCR fallback
        try:
            ocr_text = _clean_extracted_text(_extract_with_ocr(pdf_bytes))
        except Exception as e:
            if not text:
                raise ValueError(
                    f"สกัดข้อความด้วย pdfplumber ไม่ได้เลย ({reason}) และ OCR fallback ก็ล้มเหลว "
                    f"({str(e)}) — เช็คว่าติดตั้ง Tesseract OCR (พร้อม language pack 'tha') ไว้แล้วหรือยัง"
                )
            method, warning = "text_layer", f"{reason} และ OCR fallback ล้มเหลว: {str(e)}"
        else:
            # เทียบผลว่า OCR ให้ข้อความยาวกว่า (มีเนื้อหามากกว่า) ไหม ถ้าใช่ค่อยเลือกใช้แทน
            if len(ocr_text) > len(text):
                text, method, warning = ocr_text, "ocr_fallback", None
            elif not text:
                raise ValueError(
                    f"สกัดข้อความจาก PDF ไม่ได้เลยทั้ง pdfplumber และ OCR ({reason}) — "
                    "ไฟล์นี้อาจเสียหาย หรือไม่มีเนื้อหาที่อ่านได้"
                )
            else:
                method, warning = "text_layer", f"{reason} ลอง OCR แล้วแต่ผลไม่ได้ดีขึ้น จึงใช้ผลจาก pdfplumber ต่อ"

    # ขั้นดึงสกิลจากกราฟิก — ทำทีหลังสุดเสมอ เพราะต้องใช้ text สุดท้ายที่เลือกแล้ว (text_layer หรือ ocr_fallback)
    # ถ้าขั้นนี้ล้มเหลวไม่ว่าเพราะอะไร (ไม่มี API key, Gemini error, render ไม่ได้) ต้องไม่ทำให้ทั้งฟังก์ชัน error
    visual_skills: list[str] = []
    visual_detection_reason = None

    if _visual_extraction_enabled():
        try:
            visual_pages = _detect_visual_pages(pdf_bytes)
        except Exception as e:
            visual_pages = []
            warning = _append_warning(warning, f"ตรวจกราฟิกในหน้า PDF ไม่สำเร็จ: {str(e)}")

        if visual_pages:
            visual_detection_reason = "; ".join(f"หน้า {p + 1}: {r}" for p, r in visual_pages)
            try:
                text, visual_skills = _append_visual_skills(text, pdf_bytes, visual_pages)
            except Exception as e:
                warning = _append_warning(warning, f"ดึงสกิลจากกราฟิกไม่สำเร็จ จึงใช้ข้อความเดิม: {str(e)}")

    return {
        "text": text,
        "method": method,
        "warning": warning,
        "visual_skills": visual_skills,
        "visual_skills_used": len(visual_skills) > 0,
        "visual_detection_reason": visual_detection_reason,
    }


def extract_text_from_pdf_url(url: str, timeout: int = 15) -> dict:
    """
    ดาวน์โหลดไฟล์ PDF จาก url แล้วส่งต่อให้ extract_text_from_pdf_bytes สกัดข้อความ
    (แยก logic ดาวน์โหลดออกจากการสกัดข้อความ เพื่อให้ทดสอบกับไฟล์ในเครื่องผ่าน
    extract_text_from_pdf_bytes ได้โดยตรง ไม่ต้องเสิร์ฟไฟล์ขึ้น URL ก่อน)
    โยน exception ออกไปถ้าดาวน์โหลดไม่สำเร็จ หรือสกัดข้อความไม่ได้เลยทั้ง 2 วิธี
    """
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return extract_text_from_pdf_bytes(response.content)