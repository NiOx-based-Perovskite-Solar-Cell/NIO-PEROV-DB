# 🗄️ db

Template สำหรับรัน PostgreSQL ผ่าน Docker Compose พร้อมสคริปต์ Python
สำหรับสร้างตาราง (tables) หลังจากเปิดฐานข้อมูลแล้ว

## โครงสร้างโปรเจกต์

```
db/
├── docker-compose.yml          # นิยาม container ของ Postgres
├── .env.example                # ตัวอย่างค่า config (คัดลอกเป็น .env)
├── scripts/
│   ├── requirements.txt        # dependencies ของ Python
│   ├── db_connection.py        # ฟังก์ชันเชื่อมต่อฐานข้อมูล (ใช้ร่วมกันทุกสคริปต์)
│   └── example_create_users_table.py   # ตัวอย่างสคริปต์สร้างตาราง users
└── README.MD
```

## ความต้องการ (Requirements)

- [Docker](https://www.docker.com/) และ Docker Compose
- Python 3.10+

## เริ่มต้นใช้งาน

### 1. ตั้งค่า Environment

คัดลอกไฟล์ `.env.example` เป็น `.env` แล้วแก้ค่าตามต้องการ

```bash
cp .env.example .env
```

### 2. เปิดฐานข้อมูล

```bash
docker compose up -d
```

ตรวจสอบว่า container พร้อมใช้งานแล้ว:

```bash
docker compose ps
```

Postgres จะรันอยู่ที่ `localhost:5436` (ตามที่กำหนดใน `docker-compose.yml`)

### 3. ติดตั้ง dependencies ของ Python

```bash
pip install -r scripts/requirements.txt
```

### 4. รันสคริปต์สร้างตาราง

```bash
python scripts/create_users_table.py
```

สคริปต์ตัวอย่างนี้จะสร้างตาราง `users` ที่มีคอลัมน์ `username`, `email`,
`password`, `role`, `is_active`, `created_at`, `updated_at`

### 5. สร้างตารางสำหรับระบบ login (Google OAuth)

```bash
python scripts/create_auth_tables.py
```

สร้างตาราง `role`, `user_sys`, `user_identity` และเพิ่ม role เริ่มต้น
(`admin`, `professor`, `Research Assistant`, `Assistant`, `user`)
ผู้ใช้ใหม่ที่ login ด้วย Google ครั้งแรกจะได้ role `user`
รันซ้ำได้ (ไม่เขียนทับสิทธิ์ `access` ที่แก้ไขไว้แล้ว)

### 6. สร้างตารางข้อมูล perovskite

```bash
python scripts/create_data_tables.py
```

ต้องรันหลังข้อ 5 (`paper.created_by` อ้างอิง `user_sys`) สร้างตาราง lookup
(`unit`, `property`, `process_type`, `material`, `perovskite_composition`,
`vendor`, `material_source`, `solvent_system`, `solvent_component`) และตารางข้อมูล
(`paper`, `sample`, `layer`, `process_step`, `process_param`, `layer_ingredient`,
`measurement`, `stability_test`) รันซ้ำได้

## เพิ่มตารางใหม่

1. คัดลอกไฟล์ `scripts/create_users_table.py` แล้วเปลี่ยนชื่อไฟล์ตามตารางที่ต้องการ
   (เช่น `create_products_table.py`)
2. แก้ `TABLE_NAME` และ `CREATE_TABLE_SQL` ให้ตรงกับตารางใหม่
3. รันไฟล์นั้นด้วย `python scripts/<ชื่อไฟล์>.py`

สคริปต์ทุกไฟล์ใช้ `get_connection()` จาก `scripts/db_connection.py` ร่วมกัน
โดยจะอ่านค่าเชื่อมต่อจากไฟล์ `.env` ที่ root ของโปรเจกต์โดยอัตโนมัติ
