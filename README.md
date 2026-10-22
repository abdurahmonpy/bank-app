# 🏦 Bank App — Fintech Microservice (Django & JSON-RPC 2.0)

[![Django](https://img.shields.io/badge/Django-5.0+-0C4B33?logo=django)](https://www.djangoproject.com/)
[![JSON-RPC 2.0](https://img.shields.io/badge/Protocol-JSON--RPC_2.0-blue)](https://www.jsonrpc.org/specification)
[![Celery](https://img.shields.io/badge/Task_Queue-Celery-37814A?logo=celery)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Cache-Redis-DC382D?logo=redis)](https://redis.io/)
[![Unit Tests](https://img.shields.io/badge/Tests-25_Passed_100%25-brightgreen)](file:///app/tests.py)

---

## 📌 1. Loyiha Haqida (Project Overview)

Ushbu loyiha fintech sohasida bank kartalarini boshqarish, tezkor va xavfsiz P2P pul o'tkazmalarini amalga oshirish, davriy hisobotlarni Telegramga yuborish hamda ma'lumotlarni tahlil qilish uchun ishlab chiqilgan zamonaviy backend tizimidir.

### Asosiy Imkoniyatlar:
* **Kartalar boshqaruvi (Cards Management):** Luhn algoritmi bo'yicha karta validatsiyasi, avtomatik formatlash va maskalash, telefon va amal qilish muddatini normalizatsiya qilish.
* **Excel Import / Export:** Django Admin orqali Excel fayllarni yuklash, tozalash va xatoliklar hisobotini ko'rsatish; CSV va Excel formatlarida eksport qilish.
* **JSON-RPC 2.0 Microservice API:** `jsonrpcserver` kutubxonasi yordamida `transfer.create`, `transfer.confirm`, `transfer.cancel`, `transfer.state`, `transfer.history` va `card.info` metodlari.
* **2-Bosqichli Tasdiqlash (OTP):** 6 xonali tasdiqlash kodi Telegram bot orqali simulyatsiya qilinadi (maksimal 3 ta urinish).
* **Kesh Strategiyasi (Caching):** `card.info` javobi 30 soniyaga, standart xatolik xabarlari esa 300 soniyaga keshlanadi.
* **Logging va Monitoring:** Har bir so'rov bo'yicha mijoz IP manzili, ishlash davomiyligi (`duration_ms`), maskalangan parametrlar va `ext_id` orqali to'liq kuzatuvchanlik.
* **Celery & Redis Scheduler:** Har soatda jami kartalar va aylanma bo'yicha Telegram botga avtomatik hisobot yuborish.
* **Qat'iy Xavfsizlik:** CORS himoyasi, DRF Serializerlar orqali kiruvchi ma'lumotlar validatsiyasi, HMAC-SHA256 so'rov imzosi tekshiruvi, Fernet simmetrik shifrlash va Rate Limiting (5 so'rov/min).

---

## 🚀 2. O'rnatish va Sozlash (Setup Instructions)

### 2.1 Talablar:
* Python 3.11+
* Git
* Redis (mahalliy yoki Docker orqali)

### 2.2 Virtual muhitni faollashtirish va kutubxonalarni o'rnatish:
```bash
# Repository-ni klonlash
git clone https://github.com/abdurahmonpy/bank-app.git
cd bank-app

# Virtual muhit yaratish va faollashtirish
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Kerakli paketlarni o'rnatish
pip install -r requirements.txt
```

### 2.3 Muhit o'zgaruvchilari (`.env`):
Loyiha ildizida `.env` faylini yarating (namuna sifatida `.env.example` mavjud):
```env
SECRET_KEY=django-insecure-e#h!#3sl-0l8*k1nen*(33w#*#2nr9b&t_0p((9ww#39#zw1r4
DEBUG=True
ALLOWED_HOSTS=*
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
API_SECRET_KEY=super_secure_secret_for_hmac
ENCRYPTION_KEY=k1X9_J5k8Z1v3Q4_W7e2R9y8T4u1I6o3P0a2S5d8F1g=
REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

### 2.4 Ma'lumotlar bazasini sozlash:
```bash
# Migratsiyalarni qo'llash
python manage.py makemigrations
python manage.py migrate

# Standart xatolik kodlarini bazaga yuklash
python manage.py PopulateCommand

# Superuser yaratish (Admin panel uchun)
python manage.py createsuperuser
```

---

## 🏃 3. Xizmatlarni Ishga Tushirish (Running Services)

### 3.1 Django Server:
```bash
python manage.py runserver 127.0.0.1:8000
```
* **Admin Panel:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
* **JSON-RPC Endpoint:** `POST http://127.0.0.1:8000/rpc/`

### 3.2 Celery Worker va Beat (Davriy hisobotlar):
```bash
# Celery worker ishga tushirish (Windows uchun -P solo yoki threads tavsiya etiladi)
celery -A core worker -l info -P solo

# Boshqa terminalda Celery Beat (Rejalashtiruvchi):
celery -A core beat -l info
```

---

## 📡 4. JSON-RPC 2.0 API Hujjati (API Reference)

Barcha so'rovlar `POST /rpc/` manziliga `Content-Type: application/json` bilan yuboriladi.

### 4.1 `card.info` (Karta ma'lumotlari - 30s Kesh):
```json
{
  "jsonrpc": "2.0",
  "method": "card.info",
  "params": {
    "card_number": "8600 1234 1234 1234",
    "expiry": "12/26"
  },
  "id": 1
}
```
**Muvaffaqiyatli javob:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "card_number": "8600 12** **** 1234",
    "expire": "12/26",
    "phone": "+998 90 *** ** 67",
    "card_status": "active",
    "balance": 2000000.0
  },
  "id": 1
}
```

### 4.2 `transfer.create` (O'tkazma yaratish va OTP yuborish):
```json
{
  "jsonrpc": "2.0",
  "method": "transfer.create",
  "params": {
    "ext_id": "tr-uuid-001",
    "sender_card_number": "8600123412341234",
    "sender_card_expiry": "12/26",
    "receiver_card_number": "8600567812345678",
    "sending_amount": 100000,
    "currency": "860"
  },
  "id": 2
}
```
**Javob:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "ext_id": "tr-uuid-001",
    "state": "created",
    "otp_sent": true
  },
  "id": 2
}
```

### 4.3 `transfer.confirm` (O'tkazmani tasdiqlash):
```json
{
  "jsonrpc": "2.0",
  "method": "transfer.confirm",
  "params": {
    "ext_id": "tr-uuid-001",
    "otp": "123456"
  },
  "id": 3
}
```

### 4.4 `transfer.state` (Holatni tekshirish):
```json
{
  "jsonrpc": "2.0",
  "method": "transfer.state",
  "params": {
    "ext_id": "tr-uuid-001"
  },
  "id": 4
}
```

### 4.5 `transfer.cancel` (Bekor qilish):
```json
{
  "jsonrpc": "2.0",
  "method": "transfer.cancel",
  "params": {
    "ext_id": "tr-uuid-001"
  },
  "id": 5
}
```

### 4.6 `transfer.history` (Tarixni ko'rish):
```json
{
  "jsonrpc": "2.0",
  "method": "transfer.history",
  "params": {
    "card_number": "8600123412341234",
    "status": "confirmed"
  },
  "id": 6
}
```

---

## 🛠️ 5. Foydali Management Buyruqlari

```bash
# 1. Standart xatoliklarni yuklash:
python manage.py PopulateCommand

# 2. Kartalarni CSV faylga filtrlangan holda eksport qilish:
python manage.py export_cards --status=active --output=active_cards.csv

# 3. Kartalarni Excel (.xlsx) ga eksport qilish:
python manage.py export_cards_excel --output=cards.xlsx

# 4. O'tkazmalarni Excel (.xlsx) ga eksport qilish:
python manage.py export_transfers_excel --output=transfers.xlsx

# 5. Faol kartalarga simulyatsiya qilingan Telegram xabarnomasi yuborish:
python manage.py send_card_messages --status=active

# 6. Telegram davriy hisobotini darhol jo'natish:
python manage.py send_report
```

---

## 🧪 6. Avtomatlashtirilgan Testlar

Loyiha 100% testlar bilan qoplangan (jami **25 ta unit test**):
```bash
python manage.py test
```
Barcha testlar:
* Karta modellari va xossalari
* Luhn algoritmi va normalizatsiya
* Excel import/export funksiyalari
* Transfer yaratish, tasdiqlash, balans yangilanishi va bekor qilish
* Kesh mexanizmi (Redis/LocMem)
* Logging dekoratori
* HMAC-SHA256 so'rov imzosi va Rate limiting tekshiruvi.

---

## 📁 7. Qo'shimcha Hujjatlar va Fayllar
* [docs/transfer_flow.drawio](file:///docs/transfer_flow.drawio) — draw.io o'tkazmalar arxitektura diagrammasi.
* [docs/PROJECT_EXPLANATION.md](file:///docs/PROJECT_EXPLANATION.md) — Biznes vakillari va menejerlar uchun loyiha tushuntirish hujjati.
* [postman/BankApp_Collection.json](file:///postman/BankApp_Collection.json) — Postman to'plami.
* [postman/BankApp_Environment.json](file:///postman/BankApp_Environment.json) — Postman environment sozlamalari.
* [sql_queries.sql](file:///sql_queries.sql) — DataGrip uchun barcha analitik SQL so'rovlar to'plami.
