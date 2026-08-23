import os, sys, threading, webbrowser
import tkinter as tk
from tkinter import messagebox
import pystray
from PIL import Image, ImageDraw
import uvicorn

from path_utils import get_writable_config_path

# หมายเหตุ: path ของโมเดล (resume-jd-matcher-model, skill-extractor-model) ถูกจัดการ
# อยู่แล้วผ่าน path_utils.resource_path() ซึ่ง app.py และ test_full_pipeline_v4.py
# เรียกใช้ตอน import (ดูใน ensure_models_loaded() ด้านล่าง) ไม่ต้องแก้ path ในไฟล์นี้อีก

CONFIG_ENV_PATH = get_writable_config_path()

API_KEY_FIELDS = [
    ("Gemini API Key", "GEMINI_API_KEY"),
    ("OpenAI API Key", "OPENAI_API_KEY"),
    ("Anthropic (Claude) API Key", "ANTHROPIC_API_KEY"),
]


# ============================================
# 1. หน้าต่างกรอก API key ครั้งแรก (แสดงเฉพาะถ้ายังไม่เคยตั้งค่า)
# ============================================
def ensure_api_keys():
    """ถ้ายังไม่เคยกรอก key ไว้เลย ให้เปิดหน้าต่างถามก่อนเริ่ม server"""
    if os.path.exists(CONFIG_ENV_PATH):
        return  # เคยกรอกไว้แล้วรอบก่อน ไม่ต้องถามซ้ำทุกครั้งที่เปิดแอพ

    root = tk.Tk()
    root.title("ตั้งค่า API Key ครั้งแรก - Resume AI")
    root.geometry("440x300")
    root.resizable(False, False)

    tk.Label(
        root,
        text="กรอก API Key อย่างน้อย 1 ตัว เพื่อใช้งาน Storytelling Analysis\n"
             "(key จะถูกเก็บไว้ในเครื่องนี้เท่านั้น ไม่ถูกส่งไปที่ไหน)",
        wraplength=400, justify="left", pady=10
    ).pack()

    entries = {}
    for label_text, env_key in API_KEY_FIELDS:
        tk.Label(root, text=label_text, anchor="w").pack(fill="x", padx=20)
        entry = tk.Entry(root, width=55, show="*")
        entry.pack(padx=20, pady=(0, 10))
        entries[env_key] = entry

    def save_and_close():
        values = {env_key: entry.get().strip() for env_key, entry in entries.items()}
        if not any(values.values()):
            messagebox.showwarning(
                "ยังไม่ได้กรอก",
                "ต้องกรอก API Key อย่างน้อย 1 ตัวถึงจะใช้งานได้\n"
                "(ไม่รู้จะเอา key ไหนก็เว้นช่องอื่นว่างไว้ได้)"
            )
            return

        os.makedirs(os.path.dirname(CONFIG_ENV_PATH), exist_ok=True)
        with open(CONFIG_ENV_PATH, "w", encoding="utf-8") as f:
            for env_key, value in values.items():
                if value:
                    f.write(f"{env_key}={value}\n")
        root.destroy()

    def cancel():
        root.destroy()
        sys.exit(0)  # ผู้ใช้กดปิดหน้าต่างเอง ไม่ต้องเปิด server ต่อ

    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)
    tk.Button(button_frame, text="บันทึกและเริ่มใช้งาน", command=save_and_close).pack(side="left", padx=5)
    tk.Button(button_frame, text="ยกเลิก", command=cancel).pack(side="left", padx=5)

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()


# ============================================
# 2. Splash แสดงระหว่างโหลดโมเดล (SBERT + spaCy ใช้เวลาสักพัก)
# ============================================
def show_splash():
    splash = tk.Tk()
    splash.title("Resume AI API")
    splash.geometry("340x120")
    splash.resizable(False, False)
    tk.Label(
        splash,
        text="กำลังโหลดโมเดล กรุณารอสักครู่...\n(ครั้งแรกอาจใช้เวลาถึง 1 นาที)",
        pady=30, font=("Segoe UI", 10)
    ).pack()
    splash.update()  # บังคับวาดหน้าต่างทันที ก่อนจะไปทำงานที่บล็อก thread หลัก
    return splash


# ============================================
# 3. ตัว server + tray icon (เหมือนเดิม)
# ============================================
def run_server(app):
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


def create_icon_image():
    img = Image.new('RGB', (64, 64), color=(30, 144, 255))
    d = ImageDraw.Draw(img)
    d.text((18, 24), "AI", fill=(255, 255, 255))
    return img


def open_browser(icon, item):
    webbrowser.open("http://127.0.0.1:8000/docs")


def quit_app(icon, item):
    icon.stop()
    os._exit(0)


if __name__ == "__main__":
    ensure_api_keys()          # ถามครั้งแรกถ้ายังไม่เคยตั้งค่า
    splash = show_splash()     # แสดง "กำลังโหลด..." ก่อนเริ่มโหลดโมเดล

    from app import app        # import ตรงนี้ = จุดที่โมเดล SBERT/spaCy โหลดจริง (บล็อกจนเสร็จ)

    splash.destroy()           # โหลดเสร็จแล้ว ปิด splash

    server_thread = threading.Thread(target=run_server, args=(app,), daemon=True)
    server_thread.start()

    menu = pystray.Menu(
        pystray.MenuItem("Open API docs", open_browser),
        pystray.MenuItem("Quit", quit_app)
    )
    icon = pystray.Icon("resume_ai", create_icon_image(), "Resume AI API (running)", menu)

    # แจ้งเตือนแบบ balloon ว่าพร้อมใช้งานแล้ว (บาง backend ของ pystray ไม่รองรับ notify()
    # เช่นบางเวอร์ชันบน Windows เก่า ถ้าไม่รองรับก็แค่ข้ามไป ไม่ทำให้แอพ crash)
    try:
        icon.notify("โหลดโมเดลเสร็จแล้ว พร้อมใช้งานที่ localhost:8000/docs", "Resume AI API")
    except NotImplementedError:
        pass

    icon.run()