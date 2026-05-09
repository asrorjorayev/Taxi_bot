# Online Taxi Platform

Telegram orqali haydovchi va yo'lovchi e'lonlarini kerakli route bo'yicha guruhlarga yuboradigan Django + Aiogram 3 platforma.

## 1. Installation

```bash
cd online_taxi_platform
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` ichida `BOT_TOKEN`, `SECRET_KEY`, PostgreSQL va Redis sozlamalarini to'ldiring.

## 2. .env

Muhim qiymatlar:

```env
BOT_TOKEN=123456:telegram-bot-token
ADMIN_TELEGRAM_IDS=111111111,222222222
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

`ADMIN_TELEGRAM_IDS` dagi userlar botda anti-spamsiz admin hisoblanadi.

## 3. migrate

```bash
python manage.py migrate
```

## 4. seed_routes

```bash
python manage.py seed_routes
```

Bu command default route'larni yaratadi. Keyin yangi route'larni Django Admin paneldan qo'shishingiz mumkin.

## 5. create superuser

```bash
python manage.py createsuperuser
```

Admin panel: `http://localhost:8000/admin/`

## 6. run docker

```bash
docker compose up --build
```

Servislar:

- `web` - Django Admin
- `bot` - Aiogram bot
- `postgres` - database
- `redis` - FSM, Celery broker
- `celery_worker` - yuborish va repeat tasklar
- `celery_beat` - har minut repeat taskni ishga tushiradi

## 7. Botni guruhga qo'shish

1. Botni kerakli Telegram group yoki supergroup'ga qo'shing.
2. Botni admin qiling.
3. Admin user orqali guruh ichida `/register_group` yuboring.

## 8. Botni admin qilish

Telegram group settings ichida botga xabar yuborish ruxsatini bering. Admin qilinmasa e'lon yuborilmaydi va `/register_group` sababini aytadi.

## 9. /register_group

Guruh ichida:

```text
/register_group
```

Route tanlash inline keyboard chiqadi. Bitta guruh bir nechta route qabul qila oladi.

## 10. route tanlash

Route tugmalarini bosib belgilang:

```text
⬜ Bag'dod -> Toshkent
✅ Rishton -> Toshkent
⬜ Toshkent -> Bag'dod
✅ Saqlash
```

Saqlanganda `TelegramGroup.routes.set(selected_routes)` ishlaydi.

## 11. /debug_group

Guruh ichida:

```text
/debug_group
```

Ko'rsatadi:

- `chat_id`
- `title`
- `bot_is_admin`
- `is_active`
- `routes`
- `route count`

## 12. /debug_routes

Istalgan chatda:

```text
/debug_routes
```

Har route bo'yicha:

- total groups
- active groups
- bot admin groups

## 13. Repeat ishlashi uchun Celery Beat

Juda muhim: repeat e'lonlar ishlashi uchun `celery_worker` ham, `celery_beat` ham ishlab turishi shart.

Agar `celery_beat` ishlamasa:

- `process_repeating_announcements` har minut chaqirilmaydi
- 2/5/10 minutlik repeat e'lonlar qayta yuborilmaydi
- bot oddiy e'lon qabul qilishi mumkin, lekin repeat ishlamaydi

Docker bilan ikkalasi ham `docker compose up --build` orqali ishga tushadi.

## 14. Common errors

### phone after stop

Telefon handlerda `state.clear()` ishlatilmaydi. Contact va text uchun alohida handler bor:

- `F.contact`
- `F.text`

Telefon saqlangandan keyin haydovchidan mashina turi, yo'lovchidan route so'raladi.

### button not working

Har bir callback uchun handler yozilgan:

- `route:<slug>`
- `repeat_interval:0`
- `repeat_interval:2`
- `repeat_interval:5`
- `repeat_interval:10`
- `announcement_confirm`
- `announcement_cancel`
- `announcement_restart`
- `group_route_toggle:<slug>`
- `group_route_save`
- `stop_announcement:<id>`

Unhandled callback logga yoziladi.

### target group 0

Confirm paytida e'lon bazaga yoziladi va foydalanuvchiga aniq sabab chiqadi:

- route slug
- shu routega ulangan jami group count
- active group count
- bot_is_admin count

Target query:

```python
TelegramGroup.objects.filter(
    routes=announcement.route,
    is_active=True,
    bot_is_admin=True,
).distinct()
```

### repeat not working

Tekshiring:

```bash
docker compose logs celery_worker
docker compose logs celery_beat
```

`celery_beat` ishlamasa repeat task ishga tushmaydi.

### celery not running

Immediate delivery va repeat tasklar Celery orqali ishlaydi. `celery_worker` ishlamasa e'lon navbatga tushadi, lekin guruhlarga yuborilmaydi.

## Bot UX

`/start` ReplyKeyboard:

- 🚖 Haydovchi
- 🙋 Yo'lovchi
- 📋 Faol e'lonlarim
- ℹ️ Yordam
- ❌ Bekor qilish

## QA Test Checklist

1. `/start` ishlaydi.
2. Haydovchi flow oxirigacha ishlaydi.
3. Yo'lovchi flow oxirigacha ishlaydi.
4. Telefon contact ishlaydi.
5. Telefon text ishlaydi.
6. Route button ishlaydi.
7. Repeat button ishlaydi.
8. Preview chiqadi.
9. Confirm ishlaydi.
10. Announcement bazaga yoziladi.
11. Guruh route bilan ulangan bo'lsa e'lon ketadi.
12. Target group 0 bo'lsa sababini aytadi.
13. `/register_group` ishlaydi.
14. Bitta group bir nechta route oladi.
15. Repeat 2/5/10 minut ishlaydi.
16. Active announcement stop ishlaydi.
17. Admin panelda hammasi ko'rinadi.
18. Birorta unhandled callback qolmaydi, agar kutilmagan callback kelsa logga yoziladi va foydalanuvchiga javob qaytadi.

## Local run without Docker

Terminal 1:

```bash
python manage.py runserver
```

Terminal 2:

```bash
python -m bot.main
```

Terminal 3:

```bash
celery -A config.celery worker -l INFO
```

Terminal 4:

```bash
celery -A config.celery beat -l INFO
```
