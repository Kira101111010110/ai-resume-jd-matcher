# งาน: AI service แบบ .exe — หน้าเว็บ UI, ตั้งค่า key/โมเดล และเชื่อมกับเว็บที่ deploy ไว้

## บริบท
- โปรเจกต์: AI service (FastAPI) ของระบบคัดกรองเรซูเม่
  - SBERT fine-tuned → matching score
  - spaCy EntityRuler → skill extraction
  - LLM (Gemini / OpenAI / Claude) → storytelling, reasoning
- สโคปใหม่: ใช้ในรายวิชาของอาจารย์ บนเครื่อง Windows ของผู้ใช้เอง แพ็กเป็น .exe ด้วย PyInstaller
- ไฟล์หลัก:
  - `app.py` → `test_full_pipeline_v4.py` → `llm_providers.py` (import chain ต้องอยู่โฟลเดอร์เดียวกัน)
  - `pdf_extraction.py` (pdfplumber + OCR fallback ด้วย Tesseract `tha+eng`)
  - `path_utils.py` (`resource_path()`, `get_writable_config_path()` → `%APPDATA%\ResumeAI\.env`)
  - ไฟล์ `.spec` ของ PyInstaller
- ตอนนี้ยังรันด้วยคำสั่ง `uvicorn` ปกติ

## เป้าหมาย
exe ทำหน้าที่แค่รัน AI server ผู้ใช้ทำทุกอย่างผ่านหน้าเว็บที่ FastAPI เสิร์ฟเอง (ไม่เกี่ยวกับเว็บ Next.js ที่ deploy ไว้)
1. ดับเบิลคลิก exe → server โหลดโมเดล → มีไอคอนที่ system tray
2. พอ `/health` พร้อม → เปิดเบราว์เซอร์ไปหน้า UI อัตโนมัติ
3. ผู้ใช้ตั้งค่า API key + เลือกโมเดล แล้วอัปโหลด PDF วิเคราะห์ในหน้าเว็บ
4. กด "ออก" จากเมนู tray → server หยุด

> **อัปเดตรอบ 2 (โฟกัสหลักตอนนี้):** ให้ exe เชื่อมกับเว็บที่ deploy ไว้ https://resumewise-analysis.vercel.app ผ่าน ngrok tunnel — ดูหัวข้อ 8
> หัวข้อ 1–7 ทำไปแล้วในรอบแรก รอบนี้ให้ทำหัวข้อ 8 และอัปเดตส่วนที่เกี่ยวข้องในหัวข้อ 5–6 อ่านโค้ดที่ทำไปแล้วก่อนแก้
> หน้าวิเคราะห์ในเครื่อง (หัวข้อ 3) เก็บไว้ใช้ทดสอบ

## ก่อนเริ่ม
- commit สถานะปัจจุบันก่อน (หรือแตก branch ใหม่)
- อ่าน `app.py`, `llm_providers.py`, `path_utils.py`, `pdf_extraction.py`, `.spec` และ launcher ที่มีอยู่ (ถ้ามี) ให้ครบ
- **สรุปแผน + รายชื่อไฟล์ที่จะสร้าง/แก้ ให้ผู้ใช้ยืนยันก่อนลงมือแก้ไฟล์**
- ห้ามทำให้ `/analyze` เดิมเสีย (request/response เดิมต้องใช้ได้เหมือนเดิม)

---

## 1. Launcher + system tray
- รัน uvicorn ที่ `127.0.0.1` เท่านั้น ไม่ใช่ `0.0.0.0` (กันคนอื่นในวง LAN เดียวกัน เช่นห้องแล็บ เรียก API ด้วย key ของผู้ใช้หรือแก้ key ได้)
- ถ้ามี launcher (pystray / tkinter) อยู่แล้ว ให้ต่อยอดจากของเดิม ไม่ต้องเขียนใหม่
- เมนู tray: "เปิดหน้าเว็บ", "ออก"
- tooltip แสดงสถานะ: "กำลังโหลดโมเดล…" → "พร้อมใช้งาน"
- เช็ค `/health` เป็นระยะ พร้อมแล้วค่อย `webbrowser.open(...)` (ถ้าเปิดก่อนโมเดลโหลดเสร็จ หน้าจะ error)
- เปิด exe ซ้ำ: ถ้าพอร์ตถูกใช้และ `/health` ตอบได้ แปลว่ามีตัวรันอยู่แล้ว → เปิดเบราว์เซอร์แล้วปิดตัวใหม่ ถ้าไม่ใช่ → แจ้ง error ชัดเจน ห้ามตายเงียบ
- ถ้าเดิมมี dialog tkinter สำหรับใส่ key ให้เลิกใช้ ย้ายไปตั้งค่าที่หน้าเว็บที่เดียว

## 2. หน้าเว็บ (static)
- HTML / CSS / JS ล้วน ไม่มี build step ไม่โหลดจาก CDN
- ใช้ฟอนต์ระบบที่รองรับภาษาไทย (เช่น `Leelawadee UI`, `Tahoma`)
- เก็บในโฟลเดอร์ `static/` เสิร์ฟด้วย `StaticFiles` หา path ผ่าน `resource_path()` ให้ทำงานได้ทั้งตอนรัน python และตอนเป็น exe
- ถ้า `/` เดิมเป็นแค่ข้อความสถานะ ให้ `/` เสิร์ฟหน้า UI แทน ถ้ามีอะไรพึ่ง `/` อยู่ ให้ใช้ `/ui`
- 2 หน้า (หรือ 2 แท็บ): **วิเคราะห์** และ **ตั้งค่า**

## 3. หน้าวิเคราะห์ + endpoint รับไฟล์

### endpoint ใหม่ `POST /analyze-file` (multipart/form-data)
- fields: `file` (PDF), `job_title`, `faculty`, `job_text`, `model_provider` และ `model_name` (สองตัวหลังไม่บังคับ ถ้าไม่ส่งให้ใช้ค่าที่ตั้งไว้ในหน้าตั้งค่า)
- ชื่อและรูปแบบของ `job_title` / `faculty` ให้ตรงกับที่ `/analyze` รับจาก backend Node.js อยู่แล้ว (ค่าพวกนี้ใช้คำนวณ faculty penalty และ seniority)
- รับเฉพาะ PDF จำกัดขนาด (เช่น 10 MB)
- สกัดข้อความด้วย logic เดียวกับ `resume_url` (pdfplumber + OCR fallback) — ถ้า `pdf_extraction.py` ผูกกับการดาวน์โหลดจาก URL อยู่ ให้แยกฟังก์ชันสกัดจาก bytes/ไฟล์ออกมาใช้ร่วมกัน ห้าม copy โค้ดซ้ำ
- เรียก `full_analysis_pipeline()` แบบเดียวกับ `/analyze` คืน JSON โครงเดียวกัน
- ลบไฟล์ชั่วคราวหลังใช้
- เพิ่ม `python-multipart` ใน `requirements.txt` (FastAPI ต้องใช้ตอนรับ Form / UploadFile)

### หน้า UI
- ฟอร์ม: อัปโหลด PDF, ตำแหน่งงาน, คณะ/สาขาที่รับ, รายละเอียดงาน
- แสดง provider / โมเดลที่กำลังใช้ พร้อมลิงก์ไปหน้าตั้งค่า
- ถ้ายังไม่ได้ตั้ง key → ปิดปุ่มวิเคราะห์ และพาไปหน้าตั้งค่า
- ระหว่างรอ: ปิดปุ่ม + แสดงสถานะกำลังวิเคราะห์
- แสดงผลเฉพาะ field ที่มีอยู่จริงใน response (ห้ามเดา field เอง) เช่น
  - `matching_score` เป็น progress bar + `raw_matching_score`, `matching_penalty_multiplier`
  - skills (hard / soft) เป็นป้าย
  - `storytelling_score`, `ai_reason`, `specific_strengths`, `recommendation_reason`
  - `resume_quality_score`, confidence
  - `text_extraction_method` / `text_extraction_warning` (ถ้าใช้ OCR ให้แสดงคำเตือน)
- error จาก LLM (key ใช้ไม่ได้, quota เต็ม 429, โมเดลไม่มีแล้ว 404) แสดงเป็นข้อความภาษาไทยที่เข้าใจได้ พร้อมแนะนำให้ไปเปลี่ยน key / โมเดล

## 4. หน้าตั้งค่า: API key + เลือกโมเดล

### การทำงาน
- แสดง 3 provider (Gemini, OpenAI, Claude) แต่ละอันมี:
  - สถานะ: ตั้งค่าแล้ว / ยังไม่ตั้ง
  - key แบบปิดบางส่วน (เช่น `AIzaSy…x9Kq`)
  - โมเดลที่เลือก
  - ปุ่ม "เปลี่ยน key", "เปลี่ยนโมเดล", "ลบ"
- เลือก provider ที่ใช้งานหลัก (active) ได้
- ขั้นตอนใส่/เปลี่ยน key:
  1. วาง key → กด "ตรวจสอบ"
  2. key ผิด → แจ้ง error และไม่บันทึกอะไร
  3. key ถูก → ขึ้น dropdown รายชื่อโมเดล ตัว ★ แนะนำ อยู่บนสุดและถูกเลือกไว้ก่อน
  4. กด "บันทึก"
- เปลี่ยนโมเดลภายหลังได้โดยไม่ต้องใส่ key ใหม่
- ทุกการเปลี่ยนแปลงมีผลทันที ไม่ต้องรีสตาร์ท exe
- ช่องใส่ key เป็น `type="password"` มีปุ่มกดดู

### endpoints (เปลี่ยนชื่อ path ได้ถ้าชนกับของเดิม)
| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/settings` | สถานะทุก provider (configured, key แบบ mask, model) + active provider — ห้ามคืน key เต็ม |
| POST | `/api/settings/validate` | `{provider, api_key}` → ดึงรายชื่อโมเดลด้วย key นั้น → `{ok, models: [{id, label, recommended}], error}` (ยังไม่บันทึก) |
| GET | `/api/settings/{provider}/models` | ดึงรายชื่อโมเดลด้วย key ที่บันทึกไว้ (ใช้ตอนเปลี่ยนโมเดล) |
| POST | `/api/settings/save` | `{provider, api_key?, model, make_active?}` (ไม่ส่ง `api_key` = ใช้ key เดิม) |
| DELETE | `/api/settings/{provider}` | ลบ key + โมเดลของ provider นั้น |

### ดึงรายชื่อโมเดล
- ใช้ SDK เดียวกับที่ `llm_providers.py` ใช้อยู่ ตั้ง timeout ประมาณ 10 วินาที
- Gemini: list models แล้วเก็บเฉพาะตัวที่รองรับ `generateContent`
- OpenAI: list models แล้วกรองเหลือโมเดลแชต/ข้อความ ตัด embedding, tts, whisper/transcribe, image/dall-e, audio/realtime, moderation ทิ้ง
- Claude: list models (ใช้ได้ทั้งหมด)
- แยกข้อความ error ให้ต่างกัน:
  - key ไม่ถูกต้อง (เช่น Gemini 400 `API_KEY_INVALID`, OpenAI/Claude 401)
  - เน็ตมีปัญหา / timeout
  - อื่น ๆ

### ตัวแนะนำ (★)
- ค่าคงที่ `RECOMMENDED_MODELS` = รุ่นที่ใช้ทดสอบในเล่ม:
  - Gemini: `gemini-3.6-flash`
  - OpenAI: `gpt-5.6-luna`
  - Claude: `claude-sonnet-5`
- ถ้ารุ่นนั้นไม่อยู่ในลิสต์ที่ดึงมา (ชื่อโมเดลเปลี่ยนบ่อย โดยเฉพาะ Gemini):
  - Gemini → ตัวใหม่สุดที่มีคำว่า `flash`
  - Claude → ตัวใหม่สุดที่มีคำว่า `sonnet`
  - ("ใหม่สุด" ดูจากเลขเวอร์ชันในชื่อ หรือ `created_at` ถ้า API ให้มา) แล้วติด ★ ที่ตัวทดแทนนั้น
  - OpenAI → เลือกตัวแรกของลิสต์ที่กรองแล้วไว้ก่อน แต่ไม่ติด ★
- active provider ค่าเริ่มต้น: Gemini ถ้ามี key (Kappa ด้าน storytelling สูงสุด 0.542 จากการทดสอบในเล่ม)

### การเก็บค่า
- key: `%APPDATA%\ResumeAI\.env` ผ่าน `get_writable_config_path()` ที่มีอยู่
  - ชื่อตัวแปร `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (ตรวจให้ตรงกับที่ `llm_providers.py` อ่าน)
- โมเดลที่เลือก + active provider: `config.json` ในโฟลเดอร์เดียวกัน (ไม่ใช่ความลับ แยกจาก key)
- เขียนไฟล์แบบ atomic (เขียน temp แล้ว replace) กันไฟล์เสียถ้าปิดกลางคัน
- ตอนบันทึก อัปเดต `os.environ` ทันที

### ให้เปลี่ยน key แล้วมีผลทันที
- ถ้า `llm_providers.py` สร้าง client หรือเรียก `genai.configure()` ไว้ตอน import ให้เปลี่ยนเป็นสร้างตอนเรียกใช้ (หรือ cache แล้วล้าง cache เมื่อ key เปลี่ยน)
- `/analyze` เดิม: ถ้า request ไม่ระบุ provider/model ให้ใช้ค่า active จาก `config.json` ถ้าระบุมาให้ใช้ตามที่ระบุ

## 5. ความปลอดภัย
- bind `127.0.0.1` เท่านั้น
- ห้ามคืน key เต็มใน response ใด ๆ (mask = 6 ตัวแรก + `…` + 4 ตัวท้าย)
- ห้าม print / log key รวมถึงใน traceback หรือ error message ที่ส่งกลับหน้าเว็บ
- ห้าม print / log `AI_SERVICE_TOKEN` และ `NGROK_AUTHTOKEN` แบบเต็มเช่นกัน
- พอเปิด tunnel แล้ว ต้องแยกพอร์ต local / public และใช้ token ลับ (หัวข้อ 8.1–8.2)

## 6. PyInstaller
- เพิ่มโฟลเดอร์ `static/` เข้า `datas` ใน `.spec`
- เช็ค hidden imports ของ `python-multipart` (`multipart` / `python_multipart`) และ SDK ของ Gemini / OpenAI / Anthropic ว่าติดไปใน bundle
- ngrok Python SDK มีส่วนที่เป็น native (Rust) ต้องเช็คว่าไฟล์ binary ถูกเก็บเข้า bundle (ใช้ `collect_all('ngrok')` ใน `.spec` ถ้าจำเป็น)
- ทดสอบกับ exe ที่ build แล้วจริง ไม่ใช่แค่รันผ่าน python (เคยเจอ server thread ตายเงียบใน exe เพราะขาด `hiddenimports` ของ uvicorn)
- [หมายเหตุ: ถ้ายัง build แบบ `--onefile` แนะนำเปลี่ยนเป็น onedir เพราะโมเดลรวมเกิน 1 GB ต้องแตกไฟล์ลง temp ใหม่ทุกครั้งที่เปิด — ถามผู้ใช้ก่อนเปลี่ยน]

## 7. เช็คลิสต์ทดสอบ (ทั้งตอนรัน python และตอนเป็น exe)
- [ ] เครื่องที่ยังไม่มี `.env` → เปิด exe → เบราว์เซอร์เปิดเอง → หน้าวิเคราะห์บอกให้ไปตั้ง key
- [ ] ใส่ key ผิด → แจ้ง error ไม่มีอะไรถูกบันทึก
- [ ] ใส่ Gemini key ถูก → ขึ้นลิสต์โมเดลมี ★ → บันทึก → หน้าตั้งค่าแสดง key แบบ mask
- [ ] เปลี่ยน key / โมเดล → วิเคราะห์ครั้งถัดไปใช้ค่าใหม่โดยไม่ต้องรีสตาร์ท
- [ ] ลบ key → สถานะกลับเป็น "ยังไม่ตั้ง"
- [ ] อัปโหลด PDF ภาษาไทยที่ export จาก Canva → OCR fallback ทำงาน มีคำเตือนแสดง
- [ ] `/analyze` เดิม (เช่นผ่าน `call_api.py`) ยังใช้ได้
- [ ] ค้นใน response และ log ไม่เจอ key เต็ม
- [ ] เปิด exe ซ้ำขณะตัวแรกยังรัน → เปิดเบราว์เซอร์ให้ ไม่ error

## 8. เชื่อมกับเว็บที่ deploy ไว้ผ่าน ngrok tunnel (รอบ 2 — โฟกัสหลัก)

เว็บ: https://resumewise-analysis.vercel.app

ลำดับของเว็บตอนนี้: เบราว์เซอร์ → Next.js (Vercel) → backend Node.js (Render) → AI service
ปัญหา: backend บน Render มองไม่เห็น `127.0.0.1` ของเครื่องที่รัน exe
ทางที่เลือก: **exe เปิด tunnel เอง แล้วให้ Render เรียกเข้ามา**

### เหตุผลที่เลือกทางนี้
- exe เปิด ngrok ในตัวผ่าน SDK ได้เลย SDK ของ ngrok ใช้ได้ฟรีทุกแผน ([ngrok](https://ngrok.com/docs/guides/limits))
- แผนฟรีได้โดเมนประจำบัญชี 1 ชื่อที่ระบบตั้งให้ (เลือกชื่อเองไม่ได้) URL จึงไม่เปลี่ยนทุกครั้งที่รันเหมือนที่เคยเจอ ([ngrok](https://ngrok.com/docs/pricing-limits/free-plan-limits))
- ฝั่งเว็บแก้น้อยมาก แค่ตั้ง `AI_SERVICE_URL` บน Render เป็นโดเมนนั้น และแก้ `applicant.js` ที่ยัง hardcode `localhost:8000` ให้อ่านจาก env
- flow เดิมใช้ได้หมด ผลยังบันทึกลง DB ผ่าน backend ตามเดิม
- ข้อจำกัด:
  - ต้องมีเครื่องหนึ่ง (เช่นเครื่องอาจารย์) เปิด exe ทิ้งไว้ตลอดคาบ
  - ทั้งห้องใช้ LLM key ของเครื่องนั้น
  - แผนฟรีได้ 20,000 requests ต่อเดือน กับ traffic ขาออก 1GB ต่อเดือน ([ngrok](https://ngrok.com/docs/guides/other-guides/limits)) ซึ่งพอสำหรับใช้ในวิชา

### 8.1 แยกพอร์ต local กับ public
เหตุผล: request ที่มาทาง ngrok จะเข้ามาจาก `127.0.0.1` เหมือนกัน การ bind `127.0.0.1` อย่างเดียวจึงกันคนนอกเข้าหน้าตั้งค่าไม่ได้
- **พอร์ต local (ของเดิม):** หน้าวิเคราะห์, หน้าตั้งค่า, `/api/settings/*`, `/analyze-file` — ไม่ผ่าน tunnel
- **พอร์ต public (ใหม่ เช่น 8100) ที่ tunnel ชี้ไป:** มีแค่ `POST /analyze` และ `GET /health` — ห้าม mount static หรือ settings
- ทั้งสองพอร์ต bind `127.0.0.1` รันใน process เดียวกัน ใช้โมเดลที่โหลดไว้ชุดเดียว (ห้ามโหลดซ้ำ)
- `/health` ฝั่ง public คืนแค่สถานะพร้อม/ไม่พร้อม ไม่เปิดเผย provider, key หรือ path

### 8.2 token ลับระหว่าง backend กับ exe
เหตุผล: พอเปิด tunnel แล้ว ใครรู้ URL ก็เรียก `/analyze` ด้วย LLM key ของเครื่องนี้ได้
- exe สุ่ม `AI_SERVICE_TOKEN` (เช่น `secrets.token_urlsafe(32)`) ตอนเปิดครั้งแรก เก็บใน `.env` ที่ `%APPDATA%\ResumeAI\`
- `/analyze` ฝั่ง public ต้องมี header `X-AI-Token` ตรงกัน (เทียบด้วย `secrets.compare_digest`) ไม่ตรงหรือไม่มี → 401
- หน้าตั้งค่าแสดง token แบบ mask + ปุ่มคัดลอก + ปุ่มสร้างใหม่ (เตือนว่าต้องไปอัปเดตค่าบน Render ด้วย)

### 8.3 ngrok ในตัว exe
- ใช้ ngrok Python SDK (`pip install ngrok`) ไม่ต้องแนบ `ngrok.exe` แยก
- ngrok authtoken: ใส่ในหน้าตั้งค่า เก็บใน `.env` เป็น `NGROK_AUTHTOKEN` แสดงแบบ mask
- เปิด tunnel ไปที่พอร์ต public โดยใช้ dev domain ของบัญชี (แผนฟรีตั้งชื่อเองไม่ได้ ไม่ต้องส่งชื่อโดเมน) — ตรวจวิธีเรียกจาก docs ของ SDK เวอร์ชันที่ติดตั้งจริง
- หน้าตั้งค่าแสดง:
  - สถานะ tunnel: เชื่อมต่อแล้ว / ยังไม่เชื่อม / error
  - URL สาธารณะ + ปุ่มคัดลอก
  - สวิตช์เปิด/ปิด "ให้เว็บเชื่อมต่อ"
- เปิด tunnel อัตโนมัติตอนเริ่ม exe ถ้ามี authtoken และเปิดสวิตช์ไว้ tooltip ของ tray บอกสถานะ tunnel ด้วย
- tunnel หลุด → ลองต่อใหม่อัตโนมัติ และแสดงสถานะ
- ออกจาก tray → ปิด tunnel ก่อน แล้วค่อยหยุด server
- error ของ ngrok แปลเป็นข้อความไทยที่เข้าใจได้ เช่น authtoken ผิด, โดเมนถูกใช้อยู่ (เปิด exe หรือ ngrok ค้างไว้อีกเครื่อง/อีกหน้าต่างด้วยบัญชีเดียวกัน)

### 8.4 สิ่งที่ฝั่งเว็บต้องแก้ (ส่งต่อให้ทีมเว็บ — ไม่ได้อยู่ใน repo นี้ ห้ามแก้ที่นี่)
- Render environment variables:
  - `AI_SERVICE_URL` = URL ที่หน้าตั้งค่าของ exe แสดง (ไม่มี `/` ท้าย)
  - `AI_SERVICE_TOKEN` = token จากหน้าตั้งค่าของ exe
- `backend/service/applicant.js`:
  - เปลี่ยน `http://localhost:8000/analyze` → `${process.env.AI_SERVICE_URL}/analyze`
  - เพิ่ม header `X-AI-Token: process.env.AI_SERVICE_TOKEN`
  - เพิ่ม header `ngrok-skip-browser-warning: 1` (กันหน้าคั่นที่ ngrok แผนฟรีใส่ไว้)
  - ตั้ง timeout และจัดการกรณี exe ปิดอยู่หรือ tunnel ไม่ต่อ ให้แสดงข้อความ "ระบบ AI ยังไม่เปิด" แทน error ที่ไม่ชัดเจน
- ไม่ต้องแก้ CORS เพราะเป็นการเรียกจาก server (Render) ไป server (exe) ไม่ผ่านเบราว์เซอร์
- request body เดิม (`resume_url`, `job_title`, `faculty` ฯลฯ) ใช้ได้เหมือนเดิม ถ้าไม่ส่ง provider/model exe จะใช้ค่าที่ตั้งไว้ในหน้าตั้งค่า

### 8.5 เช็คลิสต์ทดสอบ
- [ ] ใส่ ngrok authtoken → tunnel ต่อได้ หน้าตั้งค่าแสดง URL สาธารณะ
- [ ] เรียก `<URL สาธารณะ>/analyze` ไม่มี token → 401, มี token ถูก → ได้ผลวิเคราะห์
- [ ] เรียก `<URL สาธารณะ>/`, `/api/settings`, `/analyze-file` → เข้าไม่ได้ (404)
- [ ] ปิด/เปิด exe ใหม่ → URL สาธารณะยังเป็นชื่อเดิม
- [ ] เว็บจริงบน Vercel: ส่งเรซูเม่ → backend บน Render เรียก exe → ผลบันทึกลง DB → HR เห็นผล
- [ ] ปิด exe ระหว่างใช้งาน → เว็บแสดงข้อความ "ระบบ AI ยังไม่เปิด" (หลังทีมเว็บแก้ตาม 8.4)
- [ ] ทดสอบทั้งหมดนี้กับ exe ที่ build แล้วจริง

## นอกขอบเขตงานนี้ (ทำแยกทีหลัง)
- แนบ Tesseract (`tesseract.exe` + `tha.traineddata` + `eng.traineddata`) ไปกับ exe สำหรับเครื่องที่ไม่ได้ติดตั้ง Tesseract
- ย้าย `google.generativeai` → `google.genai`
  - [หมายเหตุ: ถ้าย้าย SDK ทีหลัง ส่วนดึงรายชื่อโมเดลของ Gemini ต้องแก้ตามด้วย]