# -*- mode: python ; coding: utf-8 -*-
# build: ใช้ build.ps1 (สร้าง venv + เตรียม Tesseract + PyInstaller + Inno Setup)
#   หรือรันเองจากโฟลเดอร์ desktop/:  ..\.venv-build\Scripts\python -m PyInstaller --noconfirm --clean ResumeAI_API.spec
# ผลลัพธ์: desktop/dist/ResumeAI/ (ResumeAI.exe + _internal/) — installer.iss copy ทั้งโฟลเดอร์
import os
from PyInstaller.utils.hooks import collect_all

DESKTOP = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(DESKTOP)   # โค้ด AI (app.py ฯลฯ) + โมเดล อยู่ที่ root ของโปรเจกต์

# ngrok Python SDK เป็น native extension (Rust → ngrok.pyd) — เก็บทั้ง binary/data/submodule ให้ครบ
ngrok_datas, ngrok_binaries, ngrok_hiddenimports = collect_all('ngrok')

# เรซูเม่ตัวอย่าง (ปุ่ม "ลองด้วยเรซูเม่ตัวอย่าง") — รายชื่อไฟล์อยู่ใน samples.py ที่เดียว
import sys
sys.path.insert(0, DESKTOP)
sys.path.insert(0, ROOT)
import samples as _samples
sample_datas = [(os.path.join(_samples.SAMPLES_DIR, f), 'samples') for f in _samples.all_source_files()]

TESSERACT_DIR = os.path.join(DESKTOP, 'build_assets', 'tesseract')
if not os.path.exists(os.path.join(TESSERACT_DIR, 'tesseract.exe')):
    raise SystemExit("ไม่พบ build_assets/tesseract — รัน build.ps1 (ขั้นเตรียม Tesseract) ก่อน")

a = Analysis(
    [os.path.join(DESKTOP, 'launcher.py')],
    pathex=[DESKTOP, ROOT],
    binaries=ngrok_binaries,
    datas=ngrok_datas + sample_datas + [
        # โมเดล SBERT fine-tuned + spaCy EntityRuler — test_full_pipeline_v4 หา path ผ่าน resource_path()
        # (skill-extractor-model เก็บ vectors ไว้ใน vocab/ แล้ว ไม่ต้องแพ็ก en_core_web_lg แยก)
        (os.path.join(ROOT, 'resume-jd-matcher-model'), 'resume-jd-matcher-model'),
        (os.path.join(ROOT, 'skill-extractor-model'), 'skill-extractor-model'),
        # หน้าเว็บ + คู่มือ — desktop_app หา path ผ่าน bundle_path("static")
        (os.path.join(DESKTOP, 'static'), 'static'),
        # Tesseract + tha/eng/osd — bootstrap ตั้ง TESSERACT_CMD/TESSDATA_PREFIX ให้ถ้าเจอโฟลเดอร์นี้
        (TESSERACT_DIR, 'tesseract'),
        # หมายเหตุ: ไม่ bundle .env — ผู้ใช้ตั้ง API key ในหน้าเว็บ แล้วเก็บไว้ที่ %APPDATA%\ResumeAI\
    ],
    hiddenimports=[
        # โค้ด AI ที่ root — desktop_app import app ข้างในฟังก์ชัน (load_core) ระบุให้ชัด
        'app', 'error_utils', 'path_utils', 'pdf_extraction', 'llm_providers', 'test_full_pipeline_v4',
        'desktop_app', 'bootstrap', 'samples', 'settings_store', 'tunnel', 'version',
        'spacy',
        'spacy.lang.en',
        'sentence_transformers',
        'transformers',
        'torch',
        'dotenv',
        # FastAPI ต้องใช้ python-multipart ตอนรับ Form / UploadFile (/analyze-file)
        # import แบบ dynamic เลยต้องระบุเอง (ชื่อ module ใหม่ python_multipart + ชื่อเก่า multipart)
        'python_multipart',
        'multipart',
        # SDK ของ LLM ทั้ง 3 ค่าย ถูก import ข้างในฟังก์ชัน (lazy import) — ระบุให้ชัดว่าต้องติดไปด้วย
        'google.generativeai',
        'google.ai.generativelanguage',
        'google.api_core',
        'openai',
        'anthropic',
        'ngrok',
    ] + ngrok_hiddenimports + [
        # pystray บาง backend ต้องระบุเจาะจงให้ PyInstaller เห็น
        'pystray._win32',
        # uvicorn เลือก event loop / protocol implementation แบบ dynamic import
        # (importlib.import_module ผ่าน string) PyInstaller static analysis เลยมองไม่เห็น
        # module พวกนี้ ต้องระบุเจาะจงให้ครบ ไม่งั้น uvicorn.run() จะ ImportError เงียบๆ
        # ตอนรันจริงใน exe (thread ตายไม่มี error โผล่ เพราะเป็น daemon thread + windowed exe)
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # ตัดของที่ runtime ไม่ใช้ (ทดสอบแล้วว่าโหลดโมเดล/วิเคราะห์ได้โดยไม่มีตัวพวกนี้)
    # pandas ใช้แค่สคริปต์วิจัย ไม่ได้ใช้ใน API — en_core_web_lg ไม่ต้องใช้เพราะโมเดลเก็บ vectors เองแล้ว
    excludes=[
        'en_core_web_lg', 'pandas', 'matplotlib', 'tkinter', '_tkinter', 'IPython', 'jupyter_client',
        'jupyter_core', 'notebook', 'pytest', 'PyInstaller', 'torch.utils.tensorboard', 'tensorboard',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir (ไม่ใช่ onefile): โมเดลรวมเกือบ 1 GB ถ้าเป็น onefile ต้องแตกไฟล์ลง temp ใหม่ทุกครั้งที่เปิด (ช้ามาก)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ResumeAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ResumeAI',
)
