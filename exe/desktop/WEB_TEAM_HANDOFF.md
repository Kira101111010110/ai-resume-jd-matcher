# เชื่อม backend (Render) กับ AI service ที่รันบนเครื่องผู้ใช้ (exe + ngrok)

ตอนนี้ AI service (ตัววิเคราะห์เรซูเม่) รันเป็นโปรแกรม .exe บนเครื่อง Windows เครื่องหนึ่ง (เช่นเครื่องอาจารย์)
โปรแกรมเปิด ngrok tunnel ให้เอง backend บน Render จึงเรียกเข้าไปได้ผ่าน URL สาธารณะ:

```
เบราว์เซอร์ → Next.js (Vercel) → backend Node.js (Render) → https://<โดเมน ngrok>/analyze → exe บนเครื่องผู้ใช้
```

ฝั่งเว็บแก้แค่ **ไฟล์เดียว** คือ `backend/service/applicant.js` (มีไฟล์ที่แก้เสร็จแล้วให้วางทับ) + ตั้ง environment variables บน Render 2 ค่า
request body และ response ของ `/analyze` เหมือนเดิมทุกอย่าง — ไม่ต้องแก้ DB, model, route หรือหน้าเว็บ

---

## 1. ตั้ง environment variables บน Render

Render → service ของ backend → **Environment** → Add Environment Variable → Save Changes (Render deploy ใหม่ให้เอง)
ถ้ารัน backend ในเครื่อง ใส่ใน `.env` ของ backend แทน — **ห้ามเขียนค่าพวกนี้ลงในโค้ด** (token เป็นความลับ)

| ชื่อ | ค่า | เอามาจากไหน |
|---|---|---|
| `AI_SERVICE_URL` | เช่น `https://xxxx-xxxx.ngrok-free.app` (ไม่มี `/` ท้าย) | หน้าตั้งค่าของ exe → กดเปิดหัวข้อ "เชื่อมต่อกับเว็บไซต์ (ขั้นสูง)" (พับไว้ท้ายหน้า) → URL สาธารณะ → ปุ่ม "คัดลอก" |
| `AI_SERVICE_TOKEN` | สตริงสุ่มยาว 43 ตัว | หน้าตั้งค่าของ exe → "Token ลับ" → ปุ่ม "คัดลอก" |

- **ไม่ตั้งทั้งสองค่า = ทำงานแบบเดิม** (เรียก `https://duckling-hangup-resistant.ngrok-free.dev` โดยไม่ส่ง token)
  ใช้กับการรัน `uvicorn` + `ngrok` แบบที่ทำอยู่ตอนนี้ได้ ตั้งค่าเฉพาะตอนจะเปลี่ยนไปใช้ exe
- URL ไม่เปลี่ยนเมื่อปิดเปิด exe ใหม่ (ngrok แผนฟรีให้โดเมนประจำบัญชี 1 ชื่อ) ตั้งครั้งเดียวพอ
  ยกเว้นเปลี่ยนไปใช้บัญชี ngrok อื่น
- token เปลี่ยนเฉพาะตอนมีคนกด "สร้างใหม่" ในหน้าตั้งค่าของ exe ถ้ากดแล้วต้องมาอัปเดตค่าบน Render ด้วย
  ไม่งั้นทุก request จะได้ 401

---

## 2. วางทับ `backend/service/applicant.js`

ไฟล์ที่แก้เสร็จแล้ว: `desktop/web_changes/applicant.js` (ส่งมาพร้อมเอกสารนี้) — เทียบกับของเดิมด้วย diff ได้เลย
เปลี่ยนเฉพาะส่วนที่เรียก AI ส่วนอื่น (บันทึก DB, response ที่ส่งกลับหน้าเว็บ) เหมือนเดิมทุกบรรทัด:

1. URL อ่านจาก `AI_SERVICE_URL` (ไม่ตั้ง = ngrok URL เดิม)
2. ส่ง header `X-AI-Token` เมื่อตั้ง `AI_SERVICE_TOKEN` ไว้
3. timeout 180 วินาที (วิเคราะห์ปกติ 10–60 วินาที ไฟล์ที่ต้องใช้ OCR นานกว่านั้น) — เดิมไม่มี ถ้า AI ค้าง request ค้างตาม
4. error จาก AI แปลงเป็น `AppError` ที่อ่านเข้าใจ แทน error ดิบของ axios:

   | AI ตอบ | backend ตอบ | ข้อความ |
   |---|---|---|
   | 401 (token ไม่ตรง) | 503 | AI service authentication failed. Please contact the administrator. |
   | เชื่อมต่อไม่ได้ / 404 / 502 / 503 / 504 / หมดเวลา (exe ปิด, ngrok หลุด) | 503 | AI service is currently unavailable. Please try again later. |
   | 400 / 422 (เช่น อ่าน PDF ไม่ได้) | 422 | ข้อความภาษาไทยจาก AI |
   | 500 (เช่น API key ของ LLM ใช้ไม่ได้, quota เต็ม) | 502 | ข้อความภาษาไทยจาก AI |

5. `model_provider` ที่ว่าง/null ไม่ถูกส่งไป → AI ใช้ค่ายที่ตั้งไว้ในหน้าตั้งค่าของ exe
6. `skills` ไม่ crash ถ้า AI ไม่ส่ง `skills` มา

ถ้าหน้าเว็บแสดง `message` ของ error จาก backend อยู่แล้ว จะเห็นข้อความข้างบนทันที (ไม่ต้องแก้หน้าเว็บ)
แนะนำให้แสดง "ระบบ AI ยังไม่เปิด กรุณาติดต่อผู้ดูแล" เมื่อได้ 503 และไม่ควร retry รัวๆ

### request body (เหมือนเดิม)
```json
{
  "resume_url": "https://...pdf",
  "job_text": "รายละเอียดงาน",
  "job_title": "ชื่อตำแหน่ง",
  "faculty_match": "คณะ/สาขาที่ต้องการ"
}
```
- ชื่อคณะ/สาขาส่งเป็น `faculty_match` หรือ `faculty` ก็ได้ (รับทั้งสองชื่อ)
- `model_provider` / `model_name` ไม่ส่งก็ได้ ระบบจะใช้ provider และโมเดลที่ตั้งไว้ในหน้าตั้งค่าของ exe
  (ถ้าส่งมาจะใช้ตามที่ส่ง — โค้ดเดิมส่ง `post.model_provider` อยู่แล้ว ใช้ต่อได้)
- response มี field ใหม่จาก AI เวอร์ชันล่าสุด (v2.0.0): `visual_skills` (list ของทักษะที่อ่านจากกราฟิกในเรซูเม่)
  และ `visual_skills_used` (bool) — field เดิมทุกตัวยังอยู่เหมือนเดิม ไม่ต้องแก้โค้ดที่อ่าน response

---

## 3. ไม่ต้องแก้

- **CORS:** เป็นการเรียกจาก server (Render) ไป server (exe) ไม่ผ่านเบราว์เซอร์
- **การบันทึกผลลง DB:** flow เดิมใช้ได้ตามปกติ (ไม่มีคอลัมน์ใหม่ — ถ้าอยากเก็บ `visual_skills` ค่อยเพิ่มคอลัมน์ทีหลังได้ ไม่บังคับ)
- **แพ็กเกจ:** ใช้ `axios` และ `AppError` ที่มีอยู่แล้ว ไม่ต้องลงเพิ่ม

---

## 4. ข้อจำกัดที่ควรรู้

- ต้องมีเครื่องที่เปิด exe ทิ้งไว้ตลอดช่วงที่ใช้งาน ถ้าปิด เว็บจะเรียก AI ไม่ได้ (ได้ "ระบบ AI ยังไม่เปิด")
- ทุกคนที่ใช้เว็บใช้ LLM API key ของเครื่องที่รัน exe
- ngrok แผนฟรีได้ 20,000 requests และ traffic ขาออก 1 GB ต่อเดือน ซึ่งพอสำหรับใช้ในวิชา
- บัญชี ngrok เดียวเปิด tunnel ได้ทีละ 1 เครื่อง
- ถ้า AI ล้มเหลว ไฟล์เรซูเม่/transcript ถูกอัปโหลดขึ้น Cloudinary ไปแล้วแต่ไม่มีข้อมูลใน DB (โค้ดเดิมก็เป็นแบบนี้)

## 5. เช็คหลังแก้

1. เปิด exe บนเครื่องที่รัน แล้วดูว่าหน้าตั้งค่าขึ้น "เชื่อมต่อแล้ว"
2. ทดสอบจาก terminal ใดก็ได้:
   ```bash
   curl -X POST "$AI_SERVICE_URL/analyze" -H "Content-Type: application/json" \
     -H "X-AI-Token: $AI_SERVICE_TOKEN" -H "ngrok-skip-browser-warning: 1" \
     -d '{"resume_text":"Python developer with 3 years experience","job_text":"Backend developer"}'
   ```
   ต้องได้ JSON ผลวิเคราะห์ ถ้าได้ 401 แปลว่า token ไม่ตรง
3. ส่งเรซูเม่จากเว็บจริง → ผลบันทึกลง DB → HR เห็นผล
4. ปิด exe → ส่งเรซูเม่อีกครั้ง → backend ต้องตอบ 503 "AI service is currently unavailable" และไม่มีข้อมูลใหม่ใน DB
5. ตั้ง `AI_SERVICE_TOKEN` ผิดชั่วคราว → ส่งเรซูเม่ → ต้องได้ 503 "AI service authentication failed"

ยังใช้ `uvicorn` + `ngrok` แบบเดิมอยู่ (ไม่ได้ตั้ง env): ทำแค่ข้อ 3 และ 4 (ปิด uvicorn แทนการปิด exe)
