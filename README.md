# Resume Screening AI Service — คู่มือสำหรับต่อ Backend

Service นี้คือ AI layer ที่วิเคราะห์ resume เทียบกับ job description แล้วคืนผลเป็น JSON
รันแยกเป็นคนละ service จาก backend (Node.js/Next.js) — เรียกผ่าน HTTP เท่านั้น ไม่ต้องรู้ภาษา Python ก็ต่อได้

---

## วิธีรัน service (ฝั่งคนที่ดูแล Python)

```bash
pip install -r requirements.txt

# ตั้ง API key ก่อนรัน (อย่างน้อยต้องมี Gemini)
export GEMINI_API_KEY="your_key_here"      # macOS/Linux
$env:GEMINI_API_KEY="your_key_here"        # Windows PowerShell

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

ทดสอบว่า service ทำงานไหม: เปิด `http://localhost:8000/docs`

---

## Endpoint ที่ backend เรียกใช้

### `GET /health`
เช็คว่า service ยังทำงานอยู่ไหม ก่อนยิง request จริง — เรียกก่อนทุกครั้งที่ backend เริ่มทำงานก็ได้

**Response:**
```json
{ "status": "ok" }
```

### `POST /analyze`
Endpoint หลัก — ส่ง resume + job description เข้าไป ได้ผลวิเคราะห์กลับมา

**Request body:**
```json
{
  "resume_text": "ข้อความ resume เต็ม (string, ห้ามว่าง)",
  "job_text": "ข้อความ job description เต็ม (string, ห้ามว่าง)",
  "model_provider": "gemini",
  "model_name": null
}
```
- `model_provider`: `"gemini"` | `"openai"` | `"claude"` — ไม่ใส่ = ใช้ `"gemini"` (ตัวเดียวที่พร้อมใช้งานตอนนี้)
- `model_name`: ไม่ใส่ = ใช้ค่า default ของ provider นั้น (ปกติไม่ต้องใส่)

**Response (200):**
```json
{
  "matching_score": 78.5,
  "matching_confidence": 0.57,
  "skills": {
    "hard": ["AWS", "PostgreSQL", "Python", "payment processing"],
    "soft": ["Strong communication skills", "team leadership"]
  },
  "skill_extraction_confidence": 0.88,
  "storytelling_score": "High",
  "ai_reason": "...",
  "storytelling_confidence": 0.95,
  "storytelling_provider": "gemini",
  "storytelling_latency_seconds": 2.1,
  "overall_confidence": 0.78
}
```

**Error responses:**
| Code | หมายถึง | ตัวอย่าง |
|---|---|---|
| 400 | request ผิดรูปแบบ (เช่น text ว่าง หรือ provider พิมพ์ผิด) | `resume_text ห้ามว่าง` |
| 503 | provider ที่เลือกยังไม่มี API key ตั้งไว้ในเครื่องที่รัน service | `ยังไม่ได้ตั้งค่า OPENAI_API_KEY` |
| 500 | เกิด error ระหว่างวิเคราะห์ (เช่น LLM provider ล่ม/quota หมด) | รายละเอียด error แนบมาด้วย |

**สำคัญ:** backend ควร handle 503/500 ด้วยการแจ้ง user ว่า "ระบบวิเคราะห์ขัดข้องชั่วคราว ลองใหม่อีกครั้ง" ไม่ควร retry รัวๆ เพราะบาง error (เช่น quota) จะไม่หายแค่ retry เฉยๆ

---

## ตัวอย่างเรียกจาก Node.js / Next.js

```javascript
// app/api/analyze/route.js
export async function POST(req) {
  const { resumeText, jobText } = await req.json();

  const res = await fetch('http://localhost:8000/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      resume_text: resumeText,
      job_text: jobText,
      model_provider: 'gemini'
    })
  });

  if (!res.ok) {
    const err = await res.json();
    return Response.json({ error: err.detail }, { status: res.status });
  }

  const result = await res.json();
  // TODO: บันทึก result ลง MySQL ตรงนี้ก่อนส่งกลับ frontend
  return Response.json(result);
}
```

---

## CORS

Service เปิด CORS ให้ origin `http://localhost:3000` (ค่า default ของ Next.js dev) ไว้แล้ว
ถ้า frontend รันคนละพอร์ต หรือตอน deploy จริงใช้ domain อื่น ต้องแก้ใน `app.py` ตรง `allow_origins`

---

## ยังไม่รองรับตอนนี้

- `model_provider: "openai"` และ `"claude"` — โครงโค้ดพร้อมแล้ว แต่ยังไม่มี API key มาทดสอบจริง ถ้าเรียกตอนนี้จะได้ 503 กลับมา
- ไม่มี authentication บน endpoint เลย (ใครก็ยิงเข้ามาได้) — ถ้าจะขึ้น production ต้องเพิ่ม API key/token ตรวจสอบก่อนใช้งาน
