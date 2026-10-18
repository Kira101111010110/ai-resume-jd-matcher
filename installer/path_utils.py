"""
Helper กลางสำหรับหา path ที่ถูกต้อง ไม่ว่าจะรันแบบ python ปกติ หรือแบบแพ็คเป็น .exe ด้วย PyInstaller

แยกออกมาเป็นไฟล์เดี่ยวๆ (ไม่ใส่ไว้ใน app.py) เพราะ app.py และ test_full_pipeline_v4.py
ต่าง import กันไปมา (app.py -> test_full_pipeline_v4.py) ถ้าใส่ resource_path ไว้ใน
app.py แล้วให้ test_full_pipeline_v4.py import กลับมา จะเกิด circular import ทันที
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    ตอนรันแบบ python ปกติ: base_path = โฟลเดอร์ที่ไฟล์ path_utils.py นี้อยู่
    ตอนรันแบบ .exe (frozen): PyInstaller แตกไฟล์ data ทั้งหมดไปไว้ที่ sys._MEIPASS
    (โฟลเดอร์ temp ชั่วคราวที่สร้างขึ้นตอนรัน) ต้องอ้างอิงจากตรงนั้นแทน
    """
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_writable_config_path() -> str:
    """
    หา path สำหรับเก็บไฟล์ .env ที่ผู้ใช้กรอก API key เอง

    ต่างจาก resource_path() ตรงที่ path นี้ต้อง "เขียนได้และอยู่ถาวร" —
    ใช้ sys._MEIPASS ไม่ได้ เพราะมันคือ temp folder ที่ถูกลบทิ้งทุกครั้งที่ปิด .exe
    (แตกไฟล์ใหม่ทุกครั้งที่เปิด) เขียน key ลงไปแล้วจะหายตอนปิดแอพทันที

    ใช้ %APPDATA% บน Windows (หรือ home folder บน OS อื่น) ซึ่งอยู่ถาวรไม่ว่าจะ
    เปิด/ปิดแอพกี่ครั้งก็ตาม
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "ResumeAI", ".env")