# -*- coding: utf-8 -*-
"""
สร้าง resume จำลอง (synthetic) 18 ชุด สำหรับทดสอบ pipeline
ครอบคลุม: หลายสายงาน, หลายระดับประสบการณ์, สไตล์การเขียนต่างกัน (storytelling สูง/ต่ำ),
resume สั้นมาก/ยาวมาก (edge case), และ career-change

Output:
  synthetic_resumes/txt/*.txt   — ข้อความล้วน ใช้ทดสอบผ่าน resume_text ได้เลย
  synthetic_resumes/pdf/*.pdf   — ไฟล์ PDF จริง (ฝัง Sarabun font) ใช้ทดสอบผ่าน resume_url ได้
  synthetic_resumes/manifest.csv — ตารางสรุปว่าแต่ละไฟล์คือใคร/สายงานไหน/คาดหวังผลแบบไหน
  synthetic_resumes/job_descriptions.json — JD 8 ชุด ให้จับคู่ทดสอบ matching
"""

import os
import csv
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = "/home/claude/fonts"
pdfmetrics.registerFont(TTFont("Sarabun", os.path.join(FONT_DIR, "Sarabun-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Sarabun-Bold", os.path.join(FONT_DIR, "Sarabun-Bold.ttf")))

OUT_DIR = "/home/claude/synthetic_resumes"
TXT_DIR = os.path.join(OUT_DIR, "txt")
PDF_DIR = os.path.join(OUT_DIR, "pdf")

# ============================================================
# 1. ข้อมูล resume จำลอง 18 ชุด
# ============================================================
RESUMES = [
    {
        "id": "01_it_junior_high_storytelling",
        "field": "IT - Software Developer", "level": "Junior (1-2 ปี)",
        "style": "Storytelling สูง (มี Problem-Action-Result ชัดเจน)",
        "content": """สมชาย ใจดี
Junior Software Developer
อีเมล: somchai.jaidee@example.com | โทร: 08X-XXX-XXXX

แนะนำตัว
นักพัฒนาซอฟต์แวร์ที่มีประสบการณ์ 1.5 ปีด้าน Backend Development สนใจการแก้ปัญหาระบบที่ซับซ้อนและปรับปรุงประสิทธิภาพของแอปพลิเคชัน

ประสบการณ์ทำงาน
บริษัท เทคโนโลยีสตาร์ทอัพ จำกัด — Backend Developer (2566 - ปัจจุบัน)
- พบว่าระบบค้นหาสินค้าเดิมใช้เวลาตอบสนองนานถึง 3 วินาทีในช่วงที่มีผู้ใช้งานพร้อมกันจำนวนมาก ทำให้ลูกค้าบางส่วนเลิกใช้งานกลางคัน
- ทำการวิเคราะห์และพบว่าปัญหาคือการ query ฐานข้อมูลที่ไม่มี index เหมาะสม จึงออกแบบ index ใหม่และเพิ่มระบบ caching ด้วย Redis
- ผลลัพธ์: ลดเวลาตอบสนองเหลือ 400 มิลลิวินาที (ลดลง 87%) และลด load บนฐานข้อมูลหลักลง 60%
- ได้รับมอบหมายให้ดูแลระบบ payment gateway ทั้งหมด ออกแบบระบบ retry mechanism ที่ทำให้อัตราความสำเร็จของการชำระเงินเพิ่มจาก 92% เป็น 99.2%

ทักษะ
Python, Node.js, PostgreSQL, Redis, Docker, Git, RESTful API design

การศึกษา
ปริญญาตรี วิศวกรรมคอมพิวเตอร์ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี (2565)"""
    },
    {
        "id": "02_it_senior_keyword_heavy",
        "field": "IT - Software Developer", "level": "Senior (7+ ปี)",
        "style": "Storytelling ต่ำ (list keyword ล้วน ไม่มี PAR)",
        "content": """ธนกร พัฒนกิจ
Senior Software Engineer

ทักษะทางเทคนิค
Java, Spring Boot, Microservices, Kubernetes, AWS, Docker, Jenkins, CI/CD, MySQL, MongoDB, Kafka, GraphQL, Terraform, Git, Agile, Scrum

ประสบการณ์ทำงาน
บริษัท เอ็นเตอร์ไพรส์ ซอฟต์แวร์ จำกัด (2560 - ปัจจุบัน)
ตำแหน่ง Senior Software Engineer
- พัฒนาระบบ Microservices
- ดูแล Infrastructure บน AWS
- เขียน Unit Test และ Integration Test
- ทำ Code Review ให้ทีม
- เข้าร่วมประชุม Sprint Planning ทุกสัปดาห์

บริษัท ซอฟต์แวร์เฮาส์ จำกัด (2559 - 2560)
ตำแหน่ง Software Engineer
- พัฒนา Web Application ด้วย Java
- ดูแลฐานข้อมูล MySQL

การศึกษา
ปริญญาตรี วิทยาการคอมพิวเตอร์ มหาวิทยาลัยเชียงใหม่ (2559)"""
    },
    {
        "id": "03_it_data_analyst_medium",
        "field": "IT - Data Analyst", "level": "Mid (3-4 ปี)",
        "style": "Storytelling ปานกลาง (มีตัวเลขบ้าง แต่ไม่ครบ PAR ทุกจุด)",
        "content": """ปิยะดา วิเคราะห์ดี
Data Analyst

สรุปประสบการณ์
มีประสบการณ์วิเคราะห์ข้อมูลธุรกิจ 3 ปี ถนัดการใช้ SQL และ Python ในการสร้าง dashboard และรายงานสำหรับผู้บริหาร

ประสบการณ์ทำงาน
บริษัท ค้าปลีกออนไลน์ จำกัด — Data Analyst (2564 - ปัจจุบัน)
- สร้าง dashboard ยอดขายรายวันด้วย Power BI ช่วยให้ทีมผู้บริหารตัดสินใจได้เร็วขึ้น
- วิเคราะห์พฤติกรรมลูกค้าและเสนอแผนโปรโมชั่นที่ทำให้ยอดขายเพิ่มขึ้น 15% ในไตรมาสที่ผ่านมา
- ดูแลความถูกต้องของข้อมูลในคลังข้อมูล (Data Warehouse) ร่วมกับทีม Data Engineer

ทักษะ
SQL, Python, Power BI, Excel, Google Analytics, การวิเคราะห์ข้อมูลเชิงสถิติ

การศึกษา
ปริญญาตรี สถิติประยุกต์ มหาวิทยาลัยธรรมศาสตร์ (2564)"""
    },
    {
        "id": "04_accounting_entry_high_storytelling",
        "field": "Accounting", "level": "Entry (จบใหม่ - 1 ปี)",
        "style": "Storytelling สูง",
        "content": """นภัสสร บัญชีเจริญ
เจ้าหน้าที่บัญชี

แนะนำตัว
บัณฑิตจบใหม่สาขาบัญชี มีประสบการณ์ฝึกงาน 4 เดือนด้านบัญชีเจ้าหนี้ ตั้งใจพัฒนาตนเองสู่การเป็นนักบัญชีมืออาชีพ

ประสบการณ์
ฝึกงาน บริษัท ผลิตภัณฑ์อาหารไทย จำกัด (มิ.ย. - ก.ย. 2567)
- พบว่ากระบวนการตรวจสอบใบแจ้งหนี้แบบเดิมใช้เวลานานเพราะต้องเทียบเอกสารด้วยมือทีละใบ
- เสนอให้จัดทำ checklist มาตรฐานสำหรับตรวจสอบใบแจ้งหนี้ และช่วยจัดทำ Excel template ที่ทีมใช้ต่อได้
- ผลลัพธ์: ลดเวลาตรวจสอบใบแจ้งหนี้ต่อวันจากเฉลี่ย 3 ชั่วโมงเหลือ 1.5 ชั่วโมง หัวหน้างานนำ template ไปใช้ต่อทั้งแผนก

ทักษะ
Microsoft Excel (ขั้นสูง), โปรแกรมบัญชี Express, พื้นฐานภาษีมูลค่าเพิ่ม, การกระทบยอดบัญชี

การศึกษา
ปริญญาตรี บัญชีบัณฑิต มหาวิทยาลัยรามคำแหง (2567) เกรดเฉลี่ย 3.45"""
    },
    {
        "id": "05_accounting_senior_keyword",
        "field": "Accounting", "level": "Senior (8+ ปี)",
        "style": "Storytelling ต่ำ (list หน้าที่ ไม่มีผลลัพธ์เชิงตัวเลข)",
        "content": """สุรีย์พร การเงินมั่นคง
สมุห์บัญชี (Chief Accountant)

หน้าที่ความรับผิดชอบ
- ดูแลบัญชีแยกประเภททั่วไป
- จัดทำงบการเงินประจำเดือน
- ประสานงานผู้สอบบัญชี
- ดูแลทีมบัญชี 4 คน
- ยื่นภาษีประจำเดือนและประจำปี
- ตรวจสอบเอกสารทางบัญชี

ประสบการณ์ทำงาน
บริษัท อุตสาหกรรมการผลิต จำกัด (2559 - ปัจจุบัน) — สมุห์บัญชี
บริษัท การค้าระหว่างประเทศ จำกัด (2555 - 2559) — นักบัญชีอาวุโส

ทักษะ
SAP, Express, ภาษีอากร, งบการเงิน, การปิดบัญชี, Microsoft Excel

การศึกษา
ปริญญาตรี บัญชีบัณฑิต มหาวิทยาลัยกรุงเทพ (2554)"""
    },
    {
        "id": "06_marketing_mid_high_storytelling",
        "field": "Marketing", "level": "Mid (4-5 ปี)",
        "style": "Storytelling สูง (ตัวเลขผลลัพธ์ชัดเจน)",
        "content": """ณัฐพล ครีเอทีฟดี
Marketing Manager

แนะนำตัว
นักการตลาดที่เชี่ยวชาญด้าน Digital Marketing มีประสบการณ์บริหารแคมเปญโฆษณาออนไลน์งบประมาณรวมกว่า 5 ล้านบาทต่อปี

ประสบการณ์ทำงาน
บริษัท คอสเมติกไทย จำกัด — Marketing Manager (2565 - ปัจจุบัน)
- ยอดขายออนไลน์ของแบรนด์เติบโตช้าเพราะโฆษณา Facebook เดิมมี CTR ต่ำเพียง 0.8%
- ทำการทดสอบ A/B Testing ครีเอทีฟโฆษณา 6 รูปแบบ และปรับกลุ่มเป้าหมายใหม่ตามข้อมูล lookalike audience
- ผลลัพธ์: CTR เพิ่มเป็น 2.4% (เพิ่มขึ้น 3 เท่า) ต้นทุนต่อการสั่งซื้อ (CPA) ลดลง 35% ยอดขายออนไลน์ไตรมาสถัดมาเติบโต 42%
- วางแผนและบริหารทีมการตลาด 5 คน ดูแล KPI ยอดขายรวมทั้งบริษัท

ทักษะ
Facebook Ads, Google Ads, SEO, Content Marketing, Canva, Google Analytics, การบริหารทีม

การศึกษา
ปริญญาตรี นิเทศศาสตร์ จุฬาลงกรณ์มหาวิทยาลัย (2561)"""
    },
    {
        "id": "07_marketing_entry_short_edge_case",
        "field": "Marketing", "level": "Entry (จบใหม่)",
        "style": "สั้นมาก (edge case — ข้อมูลน้อย)",
        "content": """กมลชนก ตลาดใหม่
นักการตลาด (จบใหม่)
โทร: 08X-XXX-XXXX

การศึกษา
ปริญญาตรี บริหารธุรกิจ สาขาการตลาด มหาวิทยาลัยศิลปากร (2567)

ทักษะ
Canva, Facebook, Instagram

กิจกรรม
ชมรมการตลาดมหาวิทยาลัย"""
    },
    {
        "id": "08_sales_mid_high_storytelling",
        "field": "Sales", "level": "Mid (5 ปี)",
        "style": "Storytelling สูง (ตัวเลขยอดขายชัดเจน)",
        "content": """วิชัย ปิดการขายเก่ง
Senior Sales Executive

แนะนำตัว
พนักงานขายที่มีประสบการณ์ B2B Sales 5 ปีในธุรกิจอุปกรณ์อุตสาหกรรม เชี่ยวชาญการเจรจาต่อรองกับลูกค้าองค์กรขนาดใหญ่

ประสบการณ์ทำงาน
บริษัท อุปกรณ์อุตสาหกรรมไทย จำกัด — Senior Sales Executive (2562 - ปัจจุบัน)
- ได้รับมอบหมายให้ดูแลลูกค้ากลุ่มที่เคยยกเลิกสัญญาไปแล้ว 8 ราย ซึ่งบริษัทมองว่าเป็นกลุ่มเสี่ยงสูญเสียรายได้
- วางแผนเข้าพบลูกค้าเพื่อทำความเข้าใจปัญหาเดิม และเสนอแพ็กเกจบริการหลังการขายใหม่ที่ตอบโจทย์มากขึ้น
- ผลลัพธ์: ดึงลูกค้ากลับมาได้ 6 จาก 8 ราย สร้างรายได้เพิ่ม 4.2 ล้านบาทต่อปี และทำยอดขายรวมประจำปี 2567 เกินเป้า 118%

ทักษะ
การเจรจาต่อรอง B2B, CRM (Salesforce), การบริหารความสัมพันธ์ลูกค้า, การนำเสนองาน

การศึกษา
ปริญญาตรี บริหารธุรกิจ มหาวิทยาลัยขอนแก่น (2560)"""
    },
    {
        "id": "09_sales_entry_keyword",
        "field": "Sales", "level": "Entry (1 ปี)",
        "style": "Storytelling ต่ำ",
        "content": """อรุณี ขายดีมีชัย
พนักงานขาย

หน้าที่
- ขายสินค้าหน้าร้าน
- ดูแลสต๊อกสินค้า
- ต้อนรับลูกค้า
- ปิดการขาย
- จัดเรียงสินค้า

ประสบการณ์
ร้านเสื้อผ้าแฟชั่น (2566 - ปัจจุบัน) — พนักงานขาย

ทักษะ
การขาย, บริการลูกค้า, ภาษาอังกฤษเบื้องต้น

การศึกษา
ปวส. การตลาด วิทยาลัยเทคนิคนครราชสีมา (2566)"""
    },
    {
        "id": "10_customer_service_entry_short",
        "field": "Customer Service", "level": "Entry",
        "style": "สั้น เรียบง่าย",
        "content": """ศิริพร บริการดี
เจ้าหน้าที่บริการลูกค้า (Call Center)

ประสบการณ์
บริษัท ศูนย์บริการลูกค้า จำกัด (2566 - ปัจจุบัน)
รับสายลูกค้า ตอบคำถามเกี่ยวกับสินค้า บันทึกข้อมูลการร้องเรียนลงระบบ

ทักษะ
การสื่อสาร, การแก้ปัญหาเฉพาะหน้า, Microsoft Office, พิมพ์ดีดเร็ว

การศึกษา
ปริญญาตรี ศิลปศาสตร์ มหาวิทยาลัยราชภัฏสวนสุนันทา (2566)"""
    },
    {
        "id": "11_hr_mid_high_storytelling",
        "field": "Human Resources", "level": "Mid (4 ปี)",
        "style": "Storytelling สูง",
        "content": """เพ็ญพิชญา คนเก่งคัดสรร
HR Officer (Recruitment)

แนะนำตัว
เจ้าหน้าที่สรรหาบุคลากรที่มีประสบการณ์ 4 ปี เชี่ยวชาญการสรรหาตำแหน่งสาย IT และ Engineering

ประสบการณ์ทำงาน
บริษัท เทคโนโลยีการผลิต จำกัด — HR Officer (2564 - ปัจจุบัน)
- บริษัทประสบปัญหาตำแหน่ง Software Engineer ว่างนานเฉลี่ย 60 วันต่อตำแหน่ง ทำให้โปรเจกต์ล่าช้า
- ปรับกระบวนการสรรหาใหม่ ตั้งแต่การเขียน Job Description ให้ตรงเป้าหมายมากขึ้น และใช้ LinkedIn Recruiter เชิงรุกแทนการรอใบสมัคร
- ผลลัพธ์: ลดระยะเวลาสรรหาเฉลี่ยเหลือ 25 วัน (ลดลง 58%) และอัตราการลาออกภายใน 6 เดือนแรกลดลงจาก 20% เหลือ 8%

ทักษะ
การสรรหาบุคลากร, LinkedIn Recruiter, การสัมภาษณ์งาน, HRIS, กฎหมายแรงงานเบื้องต้น

การศึกษา
ปริญญาตรี จิตวิทยาอุตสาหกรรมและองค์การ มหาวิทยาลัยธรรมศาสตร์ (2563)"""
    },
    {
        "id": "12_mech_engineer_senior_keyword",
        "field": "Mechanical Engineering", "level": "Senior (9 ปี)",
        "style": "Storytelling ต่ำ, เทคนิคเข้มข้น",
        "content": """ประวิทย์ เครื่องกลชำนาญ
Senior Mechanical Engineer

ทักษะทางเทคนิค
AutoCAD, SolidWorks, GD&T, FMEA, ISO 9001, Six Sigma, PLC, การบำรุงรักษาเครื่องจักร, Hydraulics, Pneumatics

ประสบการณ์ทำงาน
บริษัท ผลิตชิ้นส่วนยานยนต์ จำกัด (2558 - ปัจจุบัน) — Senior Mechanical Engineer
- ออกแบบชิ้นส่วนเครื่องจักร
- ควบคุมมาตรฐานคุณภาพการผลิต
- ดูแลการบำรุงรักษาเชิงป้องกัน
- ฝึกอบรมทีมช่างเทคนิค

บริษัท โรงงานผลิตอุปกรณ์ไฟฟ้า จำกัด (2554 - 2558) — Mechanical Engineer
- ออกแบบและพัฒนาผลิตภัณฑ์ใหม่

การศึกษา
ปริญญาตรี วิศวกรรมเครื่องกล สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง (2554)"""
    },
    {
        "id": "13_career_change_accounting_to_it",
        "field": "IT - Career Change (จากบัญชี)", "level": "Entry ในสายใหม่",
        "style": "Career-change edge case",
        "content": """ชนากานต์ เปลี่ยนสายใหม่
ต้องการตำแหน่ง Junior Web Developer

แนะนำตัว
เคยทำงานเป็นนักบัญชี 3 ปี ปัจจุบันเปลี่ยนสายมาศึกษาการเขียนโปรแกรมด้วยตนเองและผ่านคอร์ส Bootcamp เป็นเวลา 6 เดือน ตั้งใจเริ่มต้นสายอาชีพ Web Developer

ประสบการณ์ทำงานเดิม (สายบัญชี)
บริษัท ตรวจสอบบัญชี จำกัด (2563 - 2566) — นักบัญชี
- จัดทำบัญชีและงบการเงินให้ลูกค้าหลายราย

โปรเจกต์ระหว่างเรียน Bootcamp (2567)
- พัฒนาเว็บแอปพลิเคชันจัดการงบประมาณส่วนบุคคลด้วย React และ Node.js เป็นโปรเจกต์จบคอร์ส
- ใช้ความรู้บัญชีเดิมออกแบบฟีเจอร์คำนวณรายรับ-รายจ่ายให้ตรงหลักบัญชีจริง

ทักษะใหม่
JavaScript, React, Node.js, HTML, CSS, Git, MongoDB

ทักษะเดิม
บัญชี, Excel, การวิเคราะห์ตัวเลข

การศึกษา
ปริญญาตรี บัญชีบัณฑิต มหาวิทยาลัยเกษตรศาสตร์ (2563)
ประกาศนียบัตร Full Stack Web Development Bootcamp (2567)"""
    },
    {
        "id": "14_career_change_teacher_to_hr",
        "field": "Human Resources - Career Change (จากครู)", "level": "Entry ในสายใหม่",
        "style": "Career-change edge case",
        "content": """สุพัตรา สอนดีมีสุข
ต้องการตำแหน่ง HR Coordinator

แนะนำตัว
เคยเป็นครูสอนภาษาอังกฤษระดับมัธยม 4 ปี ปัจจุบันสนใจเปลี่ยนสายมาทำงานด้านทรัพยากรบุคคล เพราะชอบงานที่เกี่ยวกับการพัฒนาคน

ประสบการณ์ทำงานเดิม
โรงเรียนมัธยมศึกษาเอกชนแห่งหนึ่ง (2563 - 2567) — ครูสอนภาษาอังกฤษ
- ออกแบบหลักสูตรและจัดกิจกรรมพัฒนาทักษะนักเรียนกว่า 200 คนต่อปี
- ดูแลและให้คำปรึกษานักเรียนเป็นรายบุคคล

ทักษะที่เกี่ยวข้อง
การสื่อสาร, การจัดการคน, การวางแผนกิจกรรม, ภาษาอังกฤษ (ดีมาก), Microsoft Office

กิจกรรมพัฒนาตนเอง
เข้าอบรมหลักสูตรการบริหารทรัพยากรบุคคลเบื้องต้น (2567)

การศึกษา
ปริญญาตรี ครุศาสตร์ สาขาภาษาอังกฤษ จุฬาลงกรณ์มหาวิทยาลัย (2563)"""
    },
    {
        "id": "15_it_very_long_senior",
        "field": "IT - Software Architect", "level": "Senior มาก (12+ ปี)",
        "style": "ยาวมาก (edge case — หลายหน้า)",
        "content": """อนุชา สถาปนิกระบบ
Software Architect

แนะนำตัว
สถาปนิกซอฟต์แวร์ที่มีประสบการณ์ 12 ปีในการออกแบบระบบขนาดใหญ่ ผ่านการทำงานทั้งสาย Fintech, E-commerce และ Enterprise Software เชี่ยวชาญการออกแบบสถาปัตยกรรมแบบ Microservices และการนำทีมทางเทคนิค

ประสบการณ์ทำงาน

บริษัท ฟินเทคชั้นนำ จำกัด — Software Architect (2563 - ปัจจุบัน)
- นำทีมออกแบบระบบใหม่ทั้งหมดจาก Monolithic เป็น Microservices เพื่อรองรับผู้ใช้งานที่เติบโตจาก 100,000 เป็น 2,000,000 คนภายใน 2 ปี
- ระบบเดิมล่มบ่อยช่วง peak time เฉลี่ยเดือนละ 3-4 ครั้ง ส่งผลกระทบต่อธุรกรรมทางการเงินของลูกค้าโดยตรง
- ออกแบบระบบใหม่โดยแยก service ตาม business domain ใช้ event-driven architecture ผ่าน Kafka และเพิ่มระบบ circuit breaker
- ผลลัพธ์: ระบบล่มเหลือ 0 ครั้งในรอบ 18 เดือนที่ผ่านมา รองรับ transaction เพิ่มขึ้น 20 เท่าโดยไม่ต้องเพิ่ม server แบบเชิงเส้น
- นำทีมวิศวกร 15 คน แบ่งเป็น 3 squad ดูแลงานคนละ domain

บริษัท อีคอมเมิร์ซรายใหญ่ จำกัด — Senior Backend Engineer / Tech Lead (2559 - 2563)
- นำทีม 6 คนพัฒนาระบบตะกร้าสินค้าและ checkout ใหม่ทั้งหมดในช่วง Double Day Sale
- ระบบเดิมรองรับ concurrent user ได้ไม่เกิน 5,000 คน ทำให้เว็บล่มทุกครั้งที่มีแคมเปญใหญ่
- ปรับสถาปัตยกรรมเป็น horizontal scaling พร้อมระบบ queue สำหรับจัดการ order
- ผลลัพธ์: รองรับ concurrent user ได้ถึง 80,000 คนในแคมเปญ 11.11 โดยไม่มีระบบล่ม ยอดขายวันเดียวทำสถิติสูงสุดของบริษัท

บริษัท ซอฟต์แวร์เอนเตอร์ไพรส์ จำกัด — Software Engineer (2555 - 2559)
- พัฒนาระบบ ERP สำหรับลูกค้าองค์กรขนาดกลาง-ใหญ่
- ดูแล module บัญชีและคลังสินค้า

ทักษะทางเทคนิค
Java, Go, Python, Kubernetes, Kafka, AWS, GCP, Terraform, PostgreSQL, Redis, gRPC, Domain-Driven Design, Event-Driven Architecture, System Design, Microservices, CI/CD

การเป็นวิทยากร
บรรยายหัวข้อ "Scaling Microservices at Fintech Scale" งาน Tech Conference ประเทศไทย (2567)
เขียนบทความเทคนิคเผยแพร่บน Medium มากกว่า 20 บทความ

การศึกษา
ปริญญาโท วิศวกรรมซอฟต์แวร์ จุฬาลงกรณ์มหาวิทยาลัย (2555)
ปริญญาตรี วิศวกรรมคอมพิวเตอร์ มหาวิทยาลัยเกษตรศาสตร์ (2553)

ใบรับรอง
AWS Certified Solutions Architect - Professional
Certified Kubernetes Administrator (CKA)"""
    },
    {
        "id": "16_fresh_grad_almost_no_experience_edge_case",
        "field": "IT - Software Developer (จบใหม่)", "level": "Entry (ไม่มีประสบการณ์ทำงาน)",
        "style": "สั้นมาก, แทบไม่มีประสบการณ์ (edge case)",
        "content": """ธีรภัทร์ จบใหม่ไฟแรง
โทร: 08X-XXX-XXXX
Email: teerapat.new@example.com

การศึกษา
ปริญญาตรี วิทยาการคอมพิวเตอร์ มหาวิทยาลัยบูรพา (2567) เกรดเฉลี่ย 2.98

ทักษะ
Python, Java เบื้องต้น, HTML, CSS

โปรเจกต์จบการศึกษา
ระบบจัดการร้านค้าออนไลน์ขนาดเล็ก (โปรเจกต์วิชาสุดท้าย)"""
    },
    {
        "id": "17_graphic_design_mixed_thai_english",
        "field": "Graphic Design", "level": "Mid (3 ปี)",
        "style": "ผสมไทย-อังกฤษ ปกติ",
        "content": """Pattarapon Creative
Graphic Designer / นักออกแบบกราฟิก

Profile
นักออกแบบกราฟิกที่มีประสบการณ์ 3 ปีด้าน Brand Identity และ Social Media Content เชี่ยวชาญ Adobe Creative Suite

Experience
Creative Agency Bangkok — Graphic Designer (2565 - Present)
- ออกแบบ Brand Identity ให้ลูกค้ากว่า 15 แบรนด์ ครอบคลุมโลโก้ Packaging และ Social Media Template
- ลูกค้ารายหนึ่งมี engagement rate ต่ำบน Instagram เฉลี่ยแค่ 1.2% จากการใช้ template เดิมที่ไม่สอดคล้องกับ brand identity
- ออกแบบ content template ใหม่ทั้งหมดให้สอดคล้องกับ brand guideline และปรับ color palette ให้ทันสมัยขึ้น
- ผลลัพธ์: engagement rate เพิ่มเป็น 4.8% ภายใน 2 เดือน ลูกค้าต่อสัญญาเพิ่มอีก 1 ปี

Skills
Adobe Photoshop, Illustrator, InDesign, Figma, Brand Identity Design, Typography, Social Media Design

การศึกษา
ปริญญาตรี ศิลปกรรมศาสตร์ สาขาออกแบบนิเทศศิลป์ มหาวิทยาลัยศิลปากร (2564)"""
    },
    {
        "id": "18_finance_analyst_high_storytelling",
        "field": "Finance - Investment Analyst", "level": "Mid (4 ปี)",
        "style": "Storytelling สูง",
        "content": """กฤษฎา วิเคราะห์การเงิน
Investment Analyst

แนะนำตัว
นักวิเคราะห์การลงทุนที่มีประสบการณ์ 4 ปีในบริษัทหลักทรัพย์ เชี่ยวชาญการวิเคราะห์หุ้นกลุ่มพลังงานและอุตสาหกรรม

ประสบการณ์ทำงาน
บริษัทหลักทรัพย์ชั้นนำ จำกัด — Investment Analyst (2564 - ปัจจุบัน)
- ทีมพบว่าบทวิเคราะห์หุ้นกลุ่มพลังงานที่ตีพิมพ์มีความแม่นยำของการคาดการณ์ราคาเป้าหมายเพียง 55% ต่ำกว่าค่าเฉลี่ยตลาด
- ปรับปรุงโมเดลการประเมินมูลค่าโดยเพิ่มปัจจัยด้านราคาพลังงานโลกและนโยบายภาครัฐเข้าไปในโมเดล DCF
- ผลลัพธ์: ความแม่นยำของการคาดการณ์เพิ่มเป็น 78% ภายใน 1 ปี บทวิเคราะห์ได้รับการอ้างอิงจากสื่อการเงินหลายครั้ง
- นำเสนอบทวิเคราะห์ต่อนักลงทุนสถาบันเป็นประจำทุกไตรมาส

ทักษะ
Financial Modeling, DCF Valuation, Bloomberg Terminal, Excel (ขั้นสูง), การวิเคราะห์งบการเงิน

การศึกษา
ปริญญาตรี การเงิน มหาวิทยาลัยธรรมศาสตร์ (2563)
ผู้สอบผ่าน CFA Level 2"""
    },
]

# ============================================================
# 2. Job Description จำลอง 8 ชุด สำหรับจับคู่ทดสอบ matching
# ============================================================
JOB_DESCRIPTIONS = {
    "jd_backend_developer": """ตำแหน่ง: Backend Developer
บริษัทซอฟต์แวร์กำลังมองหา Backend Developer ที่มีประสบการณ์ Python หรือ Node.js อย่างน้อย 1 ปี
ต้องมีความเข้าใจเรื่องฐานข้อมูล (PostgreSQL/MySQL) และการออกแบบ RESTful API
มีประสบการณ์ใช้ Docker และ Git เป็นข้อได้เปรียบ ทำงานร่วมกับทีมแบบ Agile""",

    "jd_senior_software_engineer": """ตำแหน่ง: Senior Software Engineer
ต้องการผู้มีประสบการณ์พัฒนาซอฟต์แวร์อย่างน้อย 5 ปี เชี่ยวชาญ Java/Spring Boot
มีประสบการณ์ออกแบบระบบ Microservices บน Kubernetes และ AWS
สามารถทำ Code Review และให้คำปรึกษาทีม Junior ได้""",

    "jd_data_analyst": """ตำแหน่ง: Data Analyst
มองหาผู้มีทักษะ SQL และ Python สำหรับวิเคราะห์ข้อมูลธุรกิจ
มีประสบการณ์สร้าง Dashboard ด้วย Power BI หรือ Tableau
เข้าใจสถิติเบื้องต้นและสามารถนำเสนอ Insight ให้ผู้บริหารได้""",

    "jd_accountant": """ตำแหน่ง: เจ้าหน้าที่บัญชี
รับผิดชอบงานบัญชีเจ้าหนี้-ลูกหนี้ กระทบยอดบัญชี จัดทำเอกสารทางบัญชี
ต้องมีความรู้พื้นฐานภาษีมูลค่าเพิ่ม ใช้ Excel ได้คล่อง มีความละเอียดรอบคอบ
ยินดีรับนักศึกษาจบใหม่ที่มีประสบการณ์ฝึกงานด้านบัญชี""",

    "jd_marketing_manager": """ตำแหน่ง: Marketing Manager
บริหารแคมเปญการตลาดออนไลน์ทั้ง Facebook Ads และ Google Ads
มีประสบการณ์บริหารทีมการตลาด วิเคราะห์ผล ROI ของแคมเปญ และวางกลยุทธ์การตลาดดิจิทัล
ต้องการผู้มีประสบการณ์อย่างน้อย 4 ปีในสายการตลาดดิจิทัล""",

    "jd_sales_executive": """ตำแหน่ง: Sales Executive (B2B)
ดูแลลูกค้าองค์กร เจรจาต่อรอง ปิดการขาย และรักษาความสัมพันธ์ลูกค้าเดิม
ต้องการผู้มีประสบการณ์ขายแบบ B2B อย่างน้อย 3 ปี ใช้ระบบ CRM ได้
มีทักษะการนำเสนองานและการเจรจาต่อรองที่ดี""",

    "jd_hr_recruiter": """ตำแหน่ง: HR Recruiter
รับผิดชอบการสรรหาบุคลากรตำแหน่งสาย IT และ Engineering ตั้งแต่เขียน Job Description
คัดกรองใบสมัคร นัดสัมภาษณ์ จนถึงต่อรองข้อเสนอ
มีประสบการณ์ใช้ LinkedIn Recruiter และเข้าใจ HRIS เบื้องต้น""",

    "jd_mechanical_engineer": """ตำแหน่ง: Mechanical Engineer
ออกแบบและพัฒนาชิ้นส่วนเครื่องจักรด้วย AutoCAD/SolidWorks
ควบคุมมาตรฐานคุณภาพตาม ISO 9001 ดูแลการบำรุงรักษาเครื่องจักรในโรงงาน
ต้องการผู้มีประสบการณ์อย่างน้อย 5 ปีในโรงงานอุตสาหกรรมการผลิต""",
}


def make_pdf(resume_id: str, content: str):
    path = os.path.join(PDF_DIR, f"{resume_id}.pdf")
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    normal = ParagraphStyle(
        "ThaiNormal", fontName="Sarabun", fontSize=11, leading=16, alignment=TA_LEFT
    )
    story = []
    for line in content.split("\n"):
        if line.strip() == "":
            story.append(Spacer(1, 6))
        else:
            # escape ตัวอักษรพิเศษของ XML ที่ reportlab Paragraph ใช้ตีความ markup
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line, normal))
    doc.build(story)
    return path


def main():
    os.makedirs(TXT_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)

    manifest_rows = []
    for r in RESUMES:
        txt_path = os.path.join(TXT_DIR, f"{r['id']}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(r["content"])

        pdf_path = make_pdf(r["id"], r["content"])

        manifest_rows.append({
            "id": r["id"],
            "field": r["field"],
            "level": r["level"],
            "style_note": r["style"],
            "txt_path": f"txt/{r['id']}.txt",
            "pdf_path": f"pdf/{r['id']}.pdf",
            "word_count": len(r["content"].split()),
        })
        print(f"สร้างแล้ว: {r['id']}  ({len(r['content'].split())} คำ)")

    with open(os.path.join(OUT_DIR, "manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    with open(os.path.join(OUT_DIR, "job_descriptions.json"), "w", encoding="utf-8") as f:
        json.dump(JOB_DESCRIPTIONS, f, ensure_ascii=False, indent=2)

    print(f"\nสร้าง resume ทั้งหมด {len(RESUMES)} ชุด")
    print(f"สร้าง JD ทั้งหมด {len(JOB_DESCRIPTIONS)} ชุด")
    print(f"ดูรายละเอียดที่ {os.path.join(OUT_DIR, 'manifest.csv')}")


if __name__ == "__main__":
    main()
