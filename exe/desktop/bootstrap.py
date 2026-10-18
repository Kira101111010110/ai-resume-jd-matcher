"""
ตั้งค่าที่ต้องทำ "ก่อน" import โค้ด AI (โฟลเดอร์ root) — launcher.py เรียก setup() เป็นอย่างแรก

  1. sys.path: ตอนรันแบบ dev ให้ import app.py / pdf_extraction.py ฯลฯ จากโฟลเดอร์ root ได้
  2. log: %APPDATA%\\ResumeAI\\logs\\resume_ai.log หมุนไฟล์ 5 ไฟล์ × 1 MB, ซ่อน key/token ทุกบรรทัด
  3. .env: โหลด %APPDATA%\\ResumeAI\\.env (ที่หน้าตั้งค่าบันทึก) แบบระบุ path ชัดเจน
     → llm_providers.load_dotenv() ที่รันทีหลังจะไม่ทับค่าพวกนี้ (override=False)
  4. Tesseract: ถ้ามีโฟลเดอร์ tesseract/ แนบมากับโปรแกรม ตั้ง TESSERACT_CMD + TESSDATA_PREFIX ให้ pdf_extraction ใช้
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

DESKTOP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(DESKTOP_DIR)
FROZEN = getattr(sys, "frozen", False)

APP_NAME = "Resume AI"


def bundle_path(relative_path: str) -> str:
    """ไฟล์ที่แพ็กมากับโปรแกรม (static/, samples/, tesseract/) — exe: sys._MEIPASS, dev: โฟลเดอร์ desktop/"""
    base = sys._MEIPASS if FROZEN else DESKTOP_DIR  # type: ignore[attr-defined]
    return os.path.join(base, relative_path)


def config_dir() -> str:
    """%APPDATA%\\ResumeAI — ที่เดียวกับ path_utils.get_writable_config_path() (เก็บ .env, config.json, logs)"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "ResumeAI")


LOG_DIR = os.path.join(config_dir(), "logs")
LOG_PATH = os.path.join(LOG_DIR, "resume_ai.log")


# ============================================
# log
# ============================================
class _ScrubbingFormatter(logging.Formatter):
    """ทุกบรรทัดที่ลง log ผ่าน scrub_secrets ก่อน — กัน key/token หลุดลงไฟล์ที่อาจารย์ส่งมาให้ดู"""
    def format(self, record):
        from error_utils import scrub_secrets
        return scrub_secrets(super().format(record))


class _LoggerStream:
    """แทน sys.stdout/stderr ตอนเป็น exe แบบไม่มี console (ปกติเป็น None → print/traceback พังเงียบ)
    ส่งทุกบรรทัดเข้า logging แทน จะได้ผ่านการซ่อน key และหมุนไฟล์เหมือน log อื่น"""
    def __init__(self, logger: logging.Logger, level: int):
        self._logger, self._level, self._buf = logger, level, ""
        self.encoding = "utf-8"

    def write(self, text):
        self._buf += str(text).replace("\r", "\n")   # progress bar (tqdm) ใช้ \r เขียนทับบรรทัดเดิม
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._logger.log(self._level, line.rstrip())
        return len(text)

    def flush(self):
        if self._buf.strip():
            self._logger.log(self._level, self._buf.rstrip())
        self._buf = ""

    def isatty(self):
        return False


def _setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = _ScrubbingFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1024 * 1024, backupCount=4, encoding="utf-8")
    file_handler.setFormatter(fmt)
    handlers = [file_handler]

    has_console = sys.stdout is not None and sys.stderr is not None
    if has_console:
        # รันจาก terminal: encoding อาจเป็น cp1252 → print ภาษาไทยตอนโหลดโมเดลจะ UnicodeEncodeError
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        handlers.append(console)

    root = logging.getLogger()
    root.handlers[:] = handlers
    root.setLevel(logging.INFO)
    # app.py เรียก logging.basicConfig — มี handler แล้วจึงไม่มีผล ไม่ซ้ำซ้อน

    if not has_console:
        sys.stdout = _LoggerStream(logging.getLogger("stdout"), logging.INFO)
        # stderr ส่วนใหญ่เป็นคำเตือน/progress bar ของไลบรารี ไม่ใช่ error จริง (error จริง log ผ่าน logger.exception)
        sys.stderr = _LoggerStream(logging.getLogger("stderr"), logging.WARNING)


# ============================================
# Tesseract ที่แนบมากับโปรแกรม
# ============================================
def _setup_tesseract():
    folder = bundle_path("tesseract")
    exe = os.path.join(folder, "tesseract.exe")
    if not os.path.exists(exe):
        logging.getLogger("bootstrap").info("ไม่พบ Tesseract ที่แนบมา — ใช้ Tesseract ของเครื่อง (ถ้ามี)")
        return
    os.environ["TESSERACT_CMD"] = exe
    os.environ["TESSDATA_PREFIX"] = os.path.join(folder, "tessdata")
    # DLL ของ Tesseract อยู่โฟลเดอร์เดียวกับ tesseract.exe — Windows หาเจอเองอยู่แล้ว แต่ใส่ PATH ไว้กันพลาด
    os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    logging.getLogger("bootstrap").info(f"ใช้ Tesseract ที่แนบมา: {exe}")


def setup():
    if not FROZEN and ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    _setup_logging()

    import settings_store
    settings_store.load_env_files()
    settings_store.apply_config_to_env()

    _setup_tesseract()
