# Resume AI — ตัวโปรแกรม Windows (.exe)

โฟลเดอร์นี้คือทุกอย่างที่ใช้ทำ exe + ตัวติดตั้ง โค้ด AI ที่ exe ใช้ (`app.py`, `pdf_extraction.py` ฯลฯ) อยู่ที่ `exe/` (โฟลเดอร์แม่ของ `desktop/`)
เรซูเม่ตัวอย่างใช้ชุดเดียวกับ API หลักที่ `synthetic_resumes/` ของ repo

คู่มือสำหรับผู้ใช้ (ภาษาไทย ไม่มีศัพท์เทคนิค): [`static/manual.html`](static/manual.html)

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | หน้าที่ |
|---|---|
| `launcher.py` | entry point ของ exe: ไอคอน tray + แจ้งเตือนทันที → เปิดหน้าเว็บ → เปิดเบราว์เซอร์ → โหลดโมเดล |
| `bootstrap.py` | ทำก่อน import อย่างอื่น: log หมุนไฟล์ (ซ่อน key), โหลด `%APPDATA%\ResumeAI\.env`, ตั้ง Tesseract ที่แนบมา |
| `desktop_app.py` | server หน้าเว็บ `127.0.0.1:8000`: `/analyze-file`, `/api/settings/*`, `/api/samples/*`, `/api/status` + `public_app` (พอร์ต 8100 สำหรับ ngrok) |
| `settings_store.py` | อ่าน/เขียน key (`.env`) + โมเดล/สวิตช์ (`config.json`) แล้วตั้ง env ให้โค้ด AI ทันที |
| `tunnel.py` | ngrok tunnel (ส่วนขั้นสูง ปิดเป็นค่าเริ่มต้น) |
| `samples.py` | เรซูเม่ตัวอย่าง 3 ไฟล์จาก `../../synthetic_resumes/` |
| `static/` | หน้าเว็บ (HTML/CSS/JS ไม่มี build step) + `manual.html` |
| `version.py` | เลขเวอร์ชัน (แสดงท้ายหน้าเว็บ, tooltip ของ tray, ชื่อไฟล์ติดตั้ง) |
| `ResumeAI_API.spec` | PyInstaller (onedir) |
| `installer.iss` | Inno Setup (ไม่ต้องใช้ admin) |
| `build.ps1` | build ทั้งหมดในคำสั่งเดียว |
| `requirements-desktop.txt` / `requirements-build.txt` / `requirements-lock.txt` | ของที่ exe ใช้เพิ่ม / ใช้ตอน build / เวอร์ชันที่ build จริง (pin) |
| `WEB_TEAM_HANDOFF.md` | สิ่งที่ทีมเว็บต้องแก้ ถ้าจะให้เว็บเรียก AI บนเครื่องนี้ผ่าน ngrok |

## ที่เก็บข้อมูลบนเครื่องผู้ใช้

`%APPDATA%\ResumeAI\`
- `.env` — API key ทั้ง 3 ค่าย, `AI_SERVICE_TOKEN`, `NGROK_AUTHTOKEN` (ความลับ)
- `config.json` — ค่ายหลัก, โมเดลที่เลือก, สวิตช์อ่านสกิลจากกราฟิก, สวิตช์ tunnel
- `logs\resume_ai.log` — หมุนไฟล์ 5 ไฟล์ × 1 MB, key/token ถูกแทนด้วย `AIzaSy…abcd` ทุกบรรทัด

ค่าใน `config.json` ถูกส่งให้โค้ด AI ผ่าน env: `DEFAULT_MODEL_PROVIDER`, `<PROVIDER>_MODEL_NAME`,
`VISUAL_SKILL_EXTRACTION`, `VISION_MODEL_NAME` (= โมเดล Gemini ที่เลือกไว้)

## รันแบบ dev (ไม่ต้อง build)

```powershell
# จากโฟลเดอร์ exe/
python -m venv .venv-build
.venv-build\Scripts\python -m pip install -r desktop\requirements-lock.txt
.venv-build\Scripts\python desktop\launcher.py
```
key อ่านจาก `%APPDATA%\ResumeAI\.env` ก่อน แล้วค่อย `.env` ที่ `exe/` (แบบไม่ทับ) — Tesseract ใช้ของเครื่อง

## Build exe + ตัวติดตั้ง

ต้องมี:
1. **Python 3.11+** (v2.0.0 build ด้วย Python 3.14.6)
2. **Tesseract** ของ UB-Mannheim ที่ `C:\Program Files\Tesseract-OCR` (ติ๊กภาษา Thai ตอนติดตั้ง) — https://github.com/UB-Mannheim/tesseract/wiki
3. **Inno Setup 6** — https://jrsoftware.org/isdl.php
4. โฟลเดอร์โมเดลที่ `exe/`: `resume-jd-matcher-model\` และ `skill-extractor-model\` (จาก Releases `v1.0-models`)

คำสั่งเดียว (จากโฟลเดอร์ exe/):

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build.ps1
```

ทำทีละขั้นเองก็ได้ (เหมือนที่ `build.ps1` ทำ):

```powershell
# 1) venv + แพ็กเกจ (torch แบบ CPU-only — แบบ CUDA ใหญ่หลาย GB และเครื่องผู้ใช้ไม่ต้องใช้ GPU)
py -3.14 -m venv .venv-build
.venv-build\Scripts\python -m pip install -r desktop\requirements-lock.txt
#    (อัปเดตเวอร์ชัน: pip install torch --index-url https://download.pytorch.org/whl/cpu
#     แล้ว pip install -r desktop\requirements-build.txt แล้วทำ lock ใหม่ด้วย pip freeze)

# 2) เตรียม Tesseract → desktop\build_assets\tesseract\ (tesseract.exe + DLL 33 ตัว + tha/eng/osd + license)
#    ดูรายชื่อ DLL ใน build.ps1 — ได้จาก `ldd tesseract.exe` (ไม่เอา ICU/pango ที่ใช้แค่ตอน train)

# 3) PyInstaller (onedir) → desktop\dist\ResumeAI\
cd desktop
..\.venv-build\Scripts\python -m PyInstaller --noconfirm --clean ResumeAI_API.spec

# 4) Inno Setup → desktop\Output\ResumeAI_Setup_v2.0.0.exe
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=2.0.0 installer.iss
```

สิ่งที่ตัดออกเพื่อลดขนาด: `en_core_web_lg` (โมเดล `skill-extractor-model` เก็บ vectors ไว้ใน `vocab/` เองแล้ว),
pandas, matplotlib, tkinter, IPython, pytest, tensorboard — ทดสอบแล้วว่าโหลดโมเดลและวิเคราะห์ได้ครบ

ไฟล์ติดตั้งต้องไม่เกิน 2 GB (ขีดจำกัดต่อไฟล์ของ GitHub Releases) — ถ้าเกิน เปิด `DiskSpanning=yes` ใน `installer.iss`
แล้วแจกไฟล์ `.bin` คู่กับ `.exe`

## เปลี่ยนเวอร์ชัน

แก้ `version.py` ที่เดียว — `build.ps1` ส่งเลขนี้ให้ Inno Setup และหน้าเว็บ/tray อ่านจากไฟล์นี้

## ข้อจำกัดที่รู้อยู่

- exe ไม่ได้ sign → SmartScreen เตือนตอนเปิดตัวติดตั้งครั้งแรก (วิธีกดผ่านอยู่ในคู่มือ)
- `google.generativeai` (SDK เก่า) deprecated แล้ว — ควรย้ายไป `google.genai` ก่อนเทอมหน้า
  (เวอร์ชันใน `requirements-lock.txt` ถูก pin ไว้ exe ที่ build แล้วจึงไม่เปลี่ยนตาม)
