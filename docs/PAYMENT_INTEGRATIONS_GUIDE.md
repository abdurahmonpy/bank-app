# 💳 To'lov Tizimlari Integratsiyasi Qo'llanmasi (Payment Integrations Guide)

Ushbu hujjat O'zbekiston milliy to'lov tizimlari (**Payme**, **Click**, **Upay**, **Paynet**) va xalqaro to'lov provayderi (**Stripe**) integratsiya tamoyillari, arxitekturasi va standart oqimlarini (flow) batafsil tushuntiradi.

---

## 1. To'lov Integratsiyasining Umumiy Oqimi (Standard Integration Flow)

Barcha zamonaviy to'lov provayderlari quyidagi 5 bosqichli hayot sikliga tayanadi:

```
[Mijoz (Client)] 
       │ 1. To'lov so'rovi (Amount, Service)
       ▼
[Bank App Server] ─── 2. Provider API (Create Transaction) ───► [To'lov Tizimi (PSP)]
       │                                                                │
       ▼                                                                │ 3. 2FA / OTP / 3DS
[Checkout URL / Redirect] ◄─────────────────────────────────────────────┘
       │
       ▼ 4. Foydalanuvchi to'laydi
[To'lov Tizimi (PSP)] ─── 5. Webhook Callback (Signaturali) ───► [Bank App Server]
                                                                        │
                                                                        ▼
                                                             Balans / Status Yangilanadi
```

1. **Authentication:** So'rovlarni API Key, Basic Auth (Base64) yoki Bearer Token orqali himoyalash.
2. **Create Payment:** Tranzaksiyani boshlash va unga vaqtinchalik holat (`pending` / `created`) berish.
3. **Confirm / 2FA:** Agar OTP yoki 3D-Secure talab qilinsa, tasdiqlash kodi kiritiladi.
4. **Callback / Webhook:** Provayder natijani (muvaffaqiyat yoki xatolik) serverimizning `/payment/webhook/` manziliga imzo (signature) bilan xabar qiladi.
5. **Check Payment State:** Tranzaksiya holatini tekshirish (`/payment/status?ext_id=...`).

---

## 2. O'zbekiston To'lov Tizimlari (Local Payment Service Providers)

### 2.1 Payme (Merchant API)
* **Protokol:** JSON-RPC 2.0 (HTTP POST).
* **Autentifikatsiya:** HTTP Header `Authorization: Basic Base64("Paycom:" + secret_key)`.
* **Asosiy Metodlar:**
  1. `CheckPerformTransaction`: Karta balansi, hisob raqami va summani tekshiradi. To'lash mumkin bo'lsa `allow: true` qaytaradi.
  2. `CreateTransaction`: Vaqtinchalik tranzaksiya ochadi (12 soatlik timeout bilan).
  3. `PerformTransaction`: Pulni yechib oladi va xizmatni yetkazilgan deb belgilaydi (state: 2).
  4. `CancelTransaction`: To'lovni bekor qiladi va pulni qaytaradi (refund flow).
  5. `CheckTransaction`: Tranzaksiya holati va yaratilgan vaqtini qaytaradi.
* **Xatoliklar:** Xatolik kodlari manfiy sonlarda beriladi (masalan: `-31001` buyurtma topilmadi, `-31008` amaliyot bajarib bo'lmaydi).

### 2.2 Click (Shop API)
* **Protokol:** HTTP POST (x-www-form-urlencoded yoki JSON).
* **Autentifikatsiya & Hesh:** MD5 hesh tekshiruvi:
  `sign_string = md5(click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time)`
* **Ikki bosqichli oqim:**
  1. **Prepare (`action = 0`):** Foydalanuvchi va to'lov mavjudligini tekshiradi. Agar hamma ma'lumot to'g'ri bo'lsa, `error = 0` bilan javob qaytariladi.
  2. **Complete (`action = 1`):** Pul yechildi, xizmatni ko'rsatish mumkin. To'lov tasdiqlanadi.

### 2.3 Upay va Paynet
* **Upay:** HTTP REST API orqali to'lov so'rovlari va hisob-kitoblar. Webhook callback orqali to'lov xulosasi olinadi.
* **Paynet:** Kvitansiyalarni tekshirish (Receipt Validation) va shahar bo'ylab infokiosklar orqali naqd/karta to'lovlarini qabul qilish shlyuzi.

---

## 3. Xalqaro To'lov Provayderi: Stripe API

* **Protokol:** RESTful JSON API.
* **Autentifikatsiya:** `Authorization: Bearer sk_test_...`
* **PaymentIntent Modeli:**
  1. `POST https://api.stripe.com/v1/payment_intents` (amount, currency: "usd", payment_method_types).
  2. Mijozga `client_secret` beriladi.
  3. Frontend Stripe Elements / SDK orqali 3D Secure jarayonini o'tkazadi.
  4. **Stripe Webhooks:** Provayder `payment_intent.succeeded` hodisasini yuboradi. Serverda `stripe-signature` sarlavhasi HMAC-SHA256 yordamida tekshiriladi.

---

## 4. Loyihadagi To'lov Simulyatsiyasi Endpoitlari

Bank App loyihasida yuqoridagi barcha oqimlarni to'liq qamrab oluvchi amaliy endpointlar ishlab chiqilgan:

| Endpoint | Metod | Tavsif |
|---|---|---|
| `/payment/initiate/` | POST | Yangi to'lovni yaratish va checkout URL qaytarish |
| `/payment/webhook/` | POST | Provayderdan keladigan callback/webhookni qabul qilib, holatni `success`/`failed` qilish |
| `/payment/status/` | GET | `?ext_id=pay-xxx` bo'yicha to'lov holatini tekshirish |

Ushbu modul yordamida Stripe, Payme yoki Click provayderlarini xohlagan vaqtda real rejimga biriktirish mumkin.
