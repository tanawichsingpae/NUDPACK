# 📦 NUDPACK – Dormitory Parcel Management System

ระบบจัดการพัสดุสำหรับ **หอพักนิสิต มหาวิทยาลัยนเรศวร**
พัฒนาขึ้นเพื่อแก้ปัญหาการรับ–จ่ายพัสดุที่ล่าช้า ข้อมูลตกหล่น และตรวจสอบย้อนหลังได้ยาก

---

## 📌 ภาพรวมระบบ (Overview)

NUDPACK เป็น Web Application สำหรับบริหารจัดการพัสดุภายในหอพัก
รองรับการทำงานของหลายบทบาท ได้แก่ **Admin, Client และ Recipient**

> 🎯 จุดประสงค์หลัก: ทำให้การจัดการพัสดุ “เป็นระบบ ตรวจสอบได้ และลดความผิดพลาด”

---

## 🎯 ปัญหาที่ต้องการแก้ (Problem Statement)

* ข้อมูลพัสดุจดบันทึกแบบ Manual → เกิดความผิดพลาด
* ผู้รับไม่สามารถตรวจสอบสถานะพัสดุได้
* ไม่มีระบบติดตามย้อนหลัง (Audit)
* การค้นหาพัสดุใช้เวลานาน

---

## ✨ ฟีเจอร์หลัก (Key Features)

* 🔐 ระบบ Login แยกตามบทบาท (Role-based Authentication)
* 📦 บันทึกข้อมูลพัสดุ (Tracking Number, Carrier, Status)
* 🚚 รองรับหลายบริษัทขนส่ง (DHL, Flash, J&T, KEX, SPX ฯลฯ)
* 📊 Export รายงานเป็น Excel
* 🧾 ระบบ Audit Log (ตรวจสอบประวัติการแก้ไข)
* 🔍 ค้นหาและตรวจสอบสถานะพัสดุ

---

## 👥 บทบาทผู้ใช้งาน (User Roles)

### 🛠️ Admin

* จัดการข้อมูลพัสดุทั้งหมด
* ตรวจสอบสถานะ
* ดู Audit Log
* Export รายงาน

### 🧑 Client (เจ้าหน้าที่/ผู้ดูแลหอ)

* บันทึกและจัดการพัสดุ
* ตรวจสอบข้อมูลพัสดุ

### 📬 Recipient (นิสิต)

* ตรวจสอบสถานะพัสดุของตนเอง

---

## 🛠️ เทคโนโลยีที่ใช้ (Tech Stack)

### Backend

* FastAPI
* PostgreSQL
* SQLAlchemy
* Uvicorn
* Pydantic
* Passlib (bcrypt)

### Frontend

* HTML / CSS / JavaScript

### Reporting

* Pandas
* OpenPyXL

---

## 📁 โครงสร้างโปรเจค (Project Structure)

```bash
NUDPACK-main/
│
├── client/                # หน้าเว็บผู้ใช้งาน
├── server/
│   ├── app/              # Backend (API + Logic)
│   ├── templates/        # Admin UI
│   └── static/
│
├── requirements.txt
└── README.md
```

---

## ⚙️ การติดตั้ง (Installation)

```bash
git clone <repository-url>
cd NUDPACK-main

python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

---

## 🗄️ ตั้งค่าฐานข้อมูล

แก้ไขไฟล์:

```
server/app/db.py
```

ตัวอย่าง:

```env
DATABASE_URL = "postgresql://user:password@localhost:5432/nudpack_db"
```

---

## ▶️ การรันระบบ

```bash
uvicorn server.app.main:app --reload
```

เข้าใช้งาน:

```
http://127.0.0.1:8000
```

---

## 🔐 ความปลอดภัย (Security)

* เข้ารหัสรหัสผ่านด้วย bcrypt
* ใช้ ORM ลดความเสี่ยง SQL Injection
* แยกสิทธิ์ตาม Role
* มีระบบ Audit Trail ตรวจสอบย้อนหลัง

---

## 🏫 การใช้งานจริง (Use Case)

เหมาะสำหรับ:

* หอพักนิสิต / มหาวิทยาลัย
* คอนโด / อพาร์ตเมนต์
* หน่วยงานที่มีจุดรับพัสดุส่วนกลาง

---

## 🚀 แนวทางพัฒนาต่อ (Future Improvements)

* 🔔 ระบบแจ้งเตือน (Notification)
* 🔗 เชื่อม API บริษัทขนส่ง

---

## 👨‍💻 ผู้พัฒนา

โปรเจคนี้พัฒนาจาก Requirement จริง
เพื่อแก้ปัญหาการจัดการพัสดุภายในหอพักนิสิต และสามารถต่อยอดเป็นระบบ Production ได้

---
