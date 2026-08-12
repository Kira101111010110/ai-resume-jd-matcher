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
import re
import requests
import pdfplumber
import fitz  # PyMuPDF — ใช้ render หน้า PDF เป็นรูปภาพสำหรับ OCR
import pytesseract
from PIL import Image

# สัดส่วนอักขระผิดปกติ (null byte / control char) ที่ยอมรับได้ก่อนจะถือว่า "น่าสงสัยว่าเพี้ยน"
SUSPICIOUS_CHAR_THRESHOLD = 0.001  # เกิน 0.1% ของความยาวข้อความทั้งหมด ถือว่าน่าสงสัย
MIN_WORD_COUNT = 30                # ต่ำกว่านี้ ถือว่าสกัดได้ไม่พอ (resume จริงควรมีคำมากกว่านี้มาก)


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


def extract_text_from_pdf_url(url: str, timeout: int = 15) -> dict:
    """
    ดาวน์โหลดไฟล์ PDF จาก url แล้วคืนข้อความที่สกัดได้ พร้อมข้อมูลว่าใช้วิธีไหน
    คืนค่า dict: {
        "text": str,
        "method": "text_layer" | "ocr_fallback",
        "warning": str | None   # ไม่ None ถ้าน่าสงสัยว่าข้อความยังเพี้ยนอยู่บ้าง
    }
    โยน exception ออกไปถ้าดาวน์โหลดไม่สำเร็จ หรือสกัดข้อความไม่ได้เลยทั้ง 2 วิธี
    """
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    pdf_bytes = response.content

    raw_text = _extract_with_pdfplumber(pdf_bytes)
    text = _clean_extracted_text(raw_text)

    needs_ocr, reason = _needs_ocr(raw_text)  # เช็คจากข้อความก่อน clean เพื่อนับ control char ได้ถูกต้อง

    # กรณีปกติ: pdfplumber ให้ผลดีพอ ไม่ต้องเสียเวลารัน OCR เพิ่ม
    if not needs_ocr:
        return {"text": text, "method": "text_layer", "warning": None}

    # กรณีน่าสงสัย — ลอง OCR fallback
    try:
        ocr_text = _clean_extracted_text(_extract_with_ocr(pdf_bytes))
    except Exception as e:
        if not text:
            raise ValueError(
                f"สกัดข้อความด้วย pdfplumber ไม่ได้เลย ({reason}) และ OCR fallback ก็ล้มเหลว "
                f"({str(e)}) — เช็คว่าติดตั้ง Tesseract OCR (พร้อม language pack 'tha') ไว้แล้วหรือยัง"
            )
        return {
            "text": text,
            "method": "text_layer",
            "warning": f"{reason} และ OCR fallback ล้มเหลว: {str(e)}"
        }

    # เทียบผลว่า OCR ให้ข้อความยาวกว่า (มีเนื้อหามากกว่า) ไหม ถ้าใช่ค่อยเลือกใช้แทน
    if len(ocr_text) > len(text):
        return {"text": ocr_text, "method": "ocr_fallback", "warning": None}

    if not text:
        raise ValueError(
            f"สกัดข้อความจาก PDF ไม่ได้เลยทั้ง pdfplumber และ OCR ({reason}) — "
            "ไฟล์นี้อาจเสียหาย หรือไม่มีเนื้อหาที่อ่านได้"
        )

    return {
        "text": text,
        "method": "text_layer",
        "warning": f"{reason} ลอง OCR แล้วแต่ผลไม่ได้ดีขึ้น จึงใช้ผลจาก pdfplumber ต่อ"
    }