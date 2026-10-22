# Bank App — Biznes va Loyiha Tushuntirish Hujjati (Executive Summary)

**Muallif:** Abdurahmon (Bank App Backend Team)  
**Loyiha:** Fintech Bank App (Django JSON-RPC Microservice)  
**Sana:** Oktyabr 2026  

---

## 1. Loyihaning Maqsadi va Umumiy Ko'rinishi (High-Level Overview)

Bank App loyihasi bank kartalari boshqaruvi, xavfsiz P2P pul o'tkazmalari va mikromoliyaviy tranzaksiyalarni avtomatlashtirishga mo'ljallangan backend xizmatidir. Tizim yuqori xavfsizlik (HMAC imzolash, Fernet shifrlash, Rate limiting) va yuqori tezlikka (Redis keshlash, Celery davriy hisobotlari) asoslangan holda qurilgan.

### Asosiy Modullar:
1. **Kartalar Boshqaruvi Moduli (`cards`):**
   * Bank kartalarini saqlash, amal qilish muddatlarini kuzatish, balanslar va biriktirilgan telefon raqamlarini nazorat qilish.
   * Admin panel orqali ommaviy Excel fayllarini import qilish va ma'lumotlarni normalizatsiya qilish.
   * Karta egalariga Telegram bot orqali avtomatik balans xabarnomalarini yuborish.

2. **JSON-RPC 2.0 Tranzaksiya Moduli (`transfers`):**
   * Tezkor va xalqaro standartdagi JSON-RPC 2.0 protokoli orqali P2P pul o'tkazmalarini yaratish (`transfer.create`) va tasdiqlash (`transfer.confirm`).
   * 2-bosqichli tekshiruv (2FA): har bir o'tkazma uchun 6 xonali OTP kodini generatsiya qilish va uni Telegram/SMS orqali yetkazish.
   * Tranzaksiyalar xavfsizligi: 3 martagacha noto'g'ri urinishdan so'ng avtomatik bloklash.

3. **Hisobot va Monitoring Moduli (`reports & celery`):**
   * Celery va Redis orqali har soatda rahbariyat va operatorlar uchun jami kartalar, muvaffaqiyatli o'tkazmalar va umumiy aylanma summasi bo'yicha qisqa Telegram hisobotlarini yetkazib berish.
   * Barcha o'tkazmalar va kartalar ro'yxatini tahlil qilish uchun Excel (`.xlsx`) formatiga eksport qilish.

---

## 2. Ma'lumotlar Bazasi va SQL Tahlillari (Business Analytics)

Loyiha doirasida ma'lumotlar bazasidan chuqur tahliliy ko'rsatkichlarni (insights) olish uchun tayyorlangan so'rovlar:

1. **Dublikat kartalarni aniqlash:** Bir xil karta raqamlari qayta kiritilishining oldini oladi.
2. **Faol va nofaol kartalar nisbati:** Qaysi kartalar hozirda faol to'lov qobiliyatiga ega ekanligini ko'rsatadi.
3. **Balanslar tahlili:**
   * 1,000 UZS dan past va undan yuqori balansga ega kartalar segmentatsiyasi.
   * Foydalanuvchilarni marketing kampaniyalariga ajratishda yordam beradi.
4. **O'tkazmalarda ishtirok etish ko'rsatkichi:**
   * Tizimdagi qancha karta pul o'tkazmalarida foydalanilgan va qanchasi nofaol turganligini aniqlash.
   * Qaysi mijozlar (telefon raqamlar) faol o'tkazmalarni amalga oshirayotganini hisoblash.

---

## 3. Loglar va Audit Monitoringidan Foydalanish

Har bir tranzaksiya operatsion tahlil va xavfsizlik tekshiruvi uchun maxsus dekorator orqali qayd qilinadi:
* **IP manzil bo'yicha kuzatuv:** Qaysi tarmoqdan yoki mamlakatdan so'rov kelganini bilish.
* **`ext_id` orqali treysing:** Agar mijozda shikoyat yoki savol tug'ilsa, mijoz bergan `ext_id` orqali so'rov yuborilgan sekunddan to tasdiqlanguncha bo'lgan barcha bosqichlar loglardan bir necha soniyada topiladi.
* **Ijro vaqti (Processing Time):** Har bir API chaqiruvi necha millisekundda ishlagani o'lchanadi, bu esa tizim sekinlashgan nuqtalarni darhol aniqlashga xizmat qiladi.
* **PCI-DSS xavfsizligi:** Loglarda to'liq karta raqami yoki OTP kodlari hech qachon ochiq saqlanmaydi (`8600 12** **** 9012`, `******`).

---

## 4. Eksport qilingan Excel Hisobotlari

Menejerlar va buxgalteriya bo'limi uchun qulaylik yaratish maqsadida tizimdan istalgan paytda to'liq yoki filtrlangan ma'lumotlarni yuklab olish mumkin:
* `cards_export.xlsx` — Barcha kartalar, ularning holati, balansi va egalari.
* `transfers_export.xlsx` — Har bir o'tkazmaning summasi, valyutasi, jo'natuvchi va qabul qiluvchi ma'lumotlari, sana va tasdiqlanish vaqti.
