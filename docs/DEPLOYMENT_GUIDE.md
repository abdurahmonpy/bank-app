# ☁️ Bulutga Joylashtirish Qo'llanmasi (Cloud Deployment Guide)

Ushbu hujjat **Bank App** loyihasini istalgan bulut platformasiga (Render, Railway, DigitalOcean yoki VPS) joylashtirish (deploy qilish) bo'yicha to'liq bosqichma-bosqich qo'llanmadir.

---

## 1. Render.com orqali 1-Click Deploy (Tavsiya etiladi - Bepul)

Loyiha repository'si Render uchun to'liq moslashtirilgan (`render.yaml` va `Procfile` mavjud).

### Qadamlar:
1. [Render.com](https://render.com) saytiga kiring va GitHub profilingiz orqali avtorizatsiyadan o'ting.
2. Dashboard'da **New +** $\rightarrow$ **Web Service** tugmasini bosing.
3. `https://github.com/abdurahmonpy/bank-app` repository'sini tanlang.
4. Quyidagi parametrlarni kiriting:
   * **Name:** `bank-app-api`
   * **Environment:** `Python`
   * **Region:** `Frankfurt (EU Central)` yoki `Singapore`
   * **Branch:** `main` (yoki `prod`)
   * **Build Command:**
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py PopulateCommand
     ```
   * **Start Command:**
     ```bash
     gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 3
     ```
5. **Environment Variables bo'limiga quyidagilarni qo'shing:**
   * `DEBUG` = `False`
   * `SECRET_KEY` = `django-insecure-prod-key-xyz987`
   * `ALLOWED_HOSTS` = `*`
   * `PYTHON_VERSION` = `3.12.0`
6. **Create Web Service** tugmasini bosing. 2-3 daqiqada loyiha jonli (Live) ishga tushadi:
   * Jonli havola: `https://bank-app-api.onrender.com`
   * Admin panel: `https://bank-app-api.onrender.com/admin/`
   * JSON-RPC API: `https://bank-app-api.onrender.com/rpc/`

---

## 2. Docker va Docker Compose orqali Mahalliy / VPS Serverda Joylashtirish

Loyihada konteynerlashtirish uchun tayyor `Dockerfile` va `docker-compose.yml` mavjud.

### Ishga tushirish:
```bash
# Barcha xizmatlarni (Django, Redis, Celery Worker, Celery Beat) bitta buyruq bilan ko'tarish:
docker-compose up -d --build

# Konteynerlar holatini tekshirish:
docker-compose ps

# Loglarni kuzatish:
docker-compose logs -f web
```

---

## 3. Superuser yaratish (Cloud Admin kirish ma'lumotlari)

Serverda admin foydalanuvchi yaratish uchun quyidagi buyruqni bajaring (Render Shell yoki SSH orqali):
```bash
python manage.py createsuperuser --username admin --email admin@bankapp.uz
```

---

## 4. Yakuniy Natijalar (Interview Demo uchun)

Topshiriq talabi bo'yicha taqdim etiladigan ma'lumotlar:
* **Live App URL:** `https://bank-app-api.onrender.com/rpc/`
* **Admin Panel:** `https://bank-app-api.onrender.com/admin/`
* **Postman Collection:** `postman/BankApp_Collection.json`
* **Postman Environment:** `postman/BankApp_Environment.json`
