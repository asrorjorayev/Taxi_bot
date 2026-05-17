import os

import django
from asgiref.sync import sync_to_async
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from django.conf import settings
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.taxi.log import get_logger  # noqa: E402
from apps.taxi.models import Announcement, Route, TelegramUser  # noqa: E402
from apps.taxi.services import (  # noqa: E402
    DRIVER_MANUAL_TARGET_SLUGS,
    create_announcement_from_data,
    driver_auto_direction,
)
from apps.taxi.tasks import send_announcement_task  # noqa: E402
from apps.taxi.utils import build_preview, humanize_seconds  # noqa: E402
from utils.route_formatter import route_title_for_model, route_title_for_slug  # noqa: E402
from bot.keyboards import (  # noqa: E402
    active_announcements_keyboard,
    baggage_keyboard,
    cancel_keyboard,
    confirm_keyboard,
    driver_auto_direction_keyboard,
    driver_mode_keyboard,
    gender_keyboard,
    main_menu_keyboard,
    people_count_keyboard,
    phone_keyboard,
    repeat_interval_keyboard,
    routes_keyboard,
    seats_keyboard,
    skip_photo_keyboard,
    time_keyboard,
)
from bot.states import AnnouncementStates, DriverAutoStates, DriverManualStates  # noqa: E402
from bot.utils.phone import normalize_phone  # noqa: E402

router = Router()
logger = get_logger(__name__)

SEAT_VALUES = {
    "seat_1": 1,
    "seat_2": 2,
    "seat_3": 3,
    "seat_4": 4,
}

PEOPLE_VALUES = {
    "people_1": "1",
    "people_2": "2",
    "people_3": "3",
    "people_4": "4",
    "people_post": "Pochta",
}

GENDER_VALUES = {
    "gender_male": Announcement.Gender.MALE,
    "gender_female": Announcement.Gender.FEMALE,
}

BAGGAGE_VALUES = {
    "baggage_yes": "Bor",
    "baggage_no": "Yo'q",
}

DRIVER_MANUAL_TEXTS = {"📝 E'lon qo'lda", "📝 E’lon qo‘lda", "E'lon qo'lda", "E’lon qo‘lda"}
DRIVER_AUTO_TEXTS = {"⚡ E'lon avtomatik", "⚡ E’lon avtomatik", "E'lon avtomatik", "E’lon avtomatik"}
TELEGRAM_PHOTO_CAPTION_LIMIT = 1024
TELEGRAM_MESSAGE_LIMIT = 4096


def telegram_full_name(message: Message) -> str:
    user = message.from_user
    if user.full_name and user.full_name.strip():
        return user.full_name.strip()
    if user.first_name and user.first_name.strip():
        return user.first_name.strip()
    return "Telegram foydalanuvchi"


@sync_to_async
def get_or_create_user(message: Message, role: str | None = None) -> TelegramUser:
    admin_ids = {int(item) for item in settings.ADMIN_TELEGRAM_IDS if str(item).strip().isdigit()}
    full_name = telegram_full_name(message)
    selected_role = TelegramUser.Role.ADMIN if message.from_user.id in admin_ids else role or TelegramUser.Role.PASSENGER
    user, _ = TelegramUser.objects.update_or_create(
        telegram_id=message.from_user.id,
        defaults={"full_name": full_name},
    )
    if role and user.role != TelegramUser.Role.ADMIN:
        user.role = role
    if message.from_user.id in admin_ids:
        user.role = TelegramUser.Role.ADMIN
    elif not user.role:
        user.role = selected_role
    user.full_name = full_name
    user.save(update_fields=["full_name", "role", "updated_at"])
    return user


@sync_to_async
def save_user_phone(telegram_id: int, phone: str, full_name: str, role: str) -> None:
    user, _ = TelegramUser.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={"phone": phone, "full_name": full_name},
    )
    user.phone = phone
    user.full_name = full_name
    if user.role != TelegramUser.Role.ADMIN:
        user.role = role
    user.save(update_fields=["phone", "full_name", "role", "updated_at"])


@sync_to_async
def active_routes():
    return list(Route.objects.filter(is_active=True).order_by("from_city", "to_city"))


@sync_to_async
def get_route(slug: str) -> Route:
    return Route.objects.get(slug=slug, is_active=True)


@sync_to_async
def create_announcement(data: dict, telegram_id: int) -> tuple[Announcement, dict, bool, int]:
    return create_announcement_from_data(data, telegram_id)


@sync_to_async
def user_active_announcements(telegram_id: int):
    return list(
        Announcement.objects.filter(
            user__telegram_id=telegram_id,
            status__in=[Announcement.Status.QUEUED, Announcement.Status.SENT],
        )
        .select_related("route")
        .order_by("-created_at")[:10]
    )


@sync_to_async
def stop_announcement(announcement_id: int, telegram_id: int) -> bool:
    updated = Announcement.objects.filter(
        id=announcement_id,
        user__telegram_id=telegram_id,
        status__in=[Announcement.Status.QUEUED, Announcement.Status.SENT],
    ).update(status=Announcement.Status.CANCELLED, is_repeating=False, updated_at=timezone.now())
    return bool(updated)


async def ask_route(message: Message) -> None:
    routes = await active_routes()
    if not routes:
        await message.answer("Hozircha aktiv yo'nalish yo'q. Admin paneldan route qo'shing.")
        return
    await message.answer("📍 Yo'nalishni tanlang:", reply_markup=routes_keyboard(routes))


async def ask_repeat_interval(message: Message) -> None:
    await message.answer("🔁 Qayta yuborish intervalini tanlang:", reply_markup=repeat_interval_keyboard())


def split_telegram_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def send_preview(message: Message, data: dict) -> None:
    preview = build_preview(data, data.get("route_title") or "")
    photo_file_id = data.get("car_photo_file_id")
    if photo_file_id and len(preview) <= TELEGRAM_PHOTO_CAPTION_LIMIT:
        await message.answer_photo(photo=photo_file_id, caption=preview, reply_markup=confirm_keyboard())
        return
    if photo_file_id:
        await message.answer_photo(photo=photo_file_id)
    chunks = split_telegram_text(preview)
    for chunk in chunks[:-1]:
        await message.answer(chunk)
    await message.answer(chunks[-1], reply_markup=confirm_keyboard())


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await get_or_create_user(message)
    logger.info("start", user_id=message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Taxi e'lon platformasiga xush kelibsiz.\nKerakli bo'limni tanlang:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({"ℹ️ Yordam", "â„¹ï¸ Yordam"}))
async def help_handler(message: Message) -> None:
    await message.answer(
        "E'lon berish uchun Haydovchi yoki Yo'lovchini tanlang.\n"
        "Guruh adminlari: botni guruhga admin qiling va /register_group yuboring.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({"❌ Bekor qilish", "âŒ Bekor qilish"}))
async def cancel_message_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(F.text.in_({"🚖 Haydovchi", "ðŸš– Haydovchi"}))
async def driver_start(message: Message, state: FSMContext) -> None:
    await get_or_create_user(message, TelegramUser.Role.DRIVER)
    await state.clear()
    await state.update_data(
        announcement_type=Announcement.Type.DRIVER,
        full_name=telegram_full_name(message),
        role=TelegramUser.Role.DRIVER,
    )
    logger.info("role selected", user_id=message.from_user.id, role="driver")
    await message.answer("🚕 E'lon berish usulini tanlang:", reply_markup=driver_mode_keyboard())


@router.message(F.text.in_(DRIVER_MANUAL_TEXTS))
async def driver_manual_start(message: Message, state: FSMContext) -> None:
    await get_or_create_user(message, TelegramUser.Role.DRIVER)
    await state.clear()
    await state.update_data(
        announcement_type=Announcement.Type.DRIVER,
        mode=Announcement.Mode.MANUAL,
        full_name=telegram_full_name(message),
        role=TelegramUser.Role.DRIVER,
        route_slug="bagdod_toshkent",
        route_title=route_title_for_slug("bagdod_toshkent"),
        target_route_slugs=DRIVER_MANUAL_TARGET_SLUGS,
    )
    await state.set_state(DriverManualStates.waiting_photo)
    logger.info("driver manual selected", user_id=message.from_user.id)
    await message.answer("1️⃣ Mashina rasmini yuboring:", reply_markup=cancel_keyboard())


@router.message(F.text.in_(DRIVER_AUTO_TEXTS))
async def driver_auto_start(message: Message, state: FSMContext) -> None:
    await get_or_create_user(message, TelegramUser.Role.DRIVER)
    await state.clear()
    await state.update_data(
        announcement_type=Announcement.Type.DRIVER,
        mode=Announcement.Mode.AUTO,
        full_name=telegram_full_name(message),
        role=TelegramUser.Role.DRIVER,
    )
    await state.set_state(DriverAutoStates.waiting_contact)
    logger.info("driver auto selected", user_id=message.from_user.id)
    await message.answer("1️⃣ Telefon raqamingizni contact orqali yuboring:", reply_markup=phone_keyboard())


@router.message(F.text.in_({"🙋 Yo'lovchi", "ðŸ™‹ Yo'lovchi"}))
async def passenger_start(message: Message, state: FSMContext) -> None:
    await get_or_create_user(message, TelegramUser.Role.PASSENGER)
    await state.clear()
    await state.update_data(
        announcement_type=Announcement.Type.PASSENGER,
        full_name=telegram_full_name(message),
        role=TelegramUser.Role.PASSENGER,
    )
    await state.set_state(AnnouncementStates.phone)
    logger.info("role selected", user_id=message.from_user.id, role="passenger")
    await message.answer("📞 Telefon raqamingizni yuboring yoki yozing:", reply_markup=phone_keyboard())


@router.message(F.text.in_({"📋 Faol e'lonlarim", "ðŸ“‹ Faol e'lonlarim"}))
async def active_announcements(message: Message) -> None:
    items = await user_active_announcements(message.from_user.id)
    if not items:
        await message.answer("Sizda faol e'lonlar yo'q.", reply_markup=main_menu_keyboard())
        return
    lines = ["Faol e'lonlaringiz:"]
    for item in items:
        lines.append(f"#{item.id} - {item.route_title or '-'} - {item.get_status_display()}")
    await message.answer("\n".join(lines), reply_markup=active_announcements_keyboard(items))


@router.message(DriverManualStates.waiting_photo, F.photo)
async def driver_manual_photo_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(car_photo_file_id=message.photo[-1].file_id)
    await state.set_state(DriverManualStates.waiting_text)
    await message.answer(
        "✅ Rasm qabul qilindi.\n\n2️⃣ Endi e'lon matnini yuboring:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(DriverManualStates.waiting_photo)
async def driver_manual_wrong_photo_handler(message: Message) -> None:
    await message.answer("Mashina rasmini yuboring:", reply_markup=cancel_keyboard())


@router.message(DriverManualStates.waiting_text, F.text)
async def driver_manual_text_handler(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("E'lon matnini to'liqroq yozing.")
        return
    await state.update_data(manual_text=text)
    await state.set_state(DriverManualStates.waiting_interval)
    await ask_repeat_interval(message)


@router.message(DriverManualStates.waiting_text)
async def driver_manual_wrong_text_handler(message: Message) -> None:
    await message.answer("E'lon matnini oddiy text ko'rinishida yuboring.")


async def after_phone_saved(message: Message, state: FSMContext, phone: str) -> None:
    data = await state.get_data()
    full_name = data.get("full_name") or telegram_full_name(message)
    await save_user_phone(message.from_user.id, phone, full_name, data["role"])
    await state.update_data(phone=phone, full_name=full_name)
    logger.info("phone received", user_id=message.from_user.id, phone=phone)
    if data["role"] == TelegramUser.Role.DRIVER:
        await state.set_state(DriverAutoStates.waiting_car_type)
        await message.answer(
            "2️⃣ Mashina turini kiriting. Masalan: Cobalt",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_state(AnnouncementStates.route)
    await message.answer("✅ Telefon qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await ask_route(message)


@router.message(AnnouncementStates.phone, F.contact)
@router.message(DriverAutoStates.waiting_contact, F.contact)
async def phone_contact_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        await message.answer("Telefon raqam noto'g'ri. Masalan: +998901234567")
        return
    await after_phone_saved(message, state, phone)


@router.message(AnnouncementStates.phone, F.text)
@router.message(DriverAutoStates.waiting_contact, F.text)
async def phone_text_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer("Telefon raqam noto'g'ri. Qabul qilinadi: +998901234567, 998901234567, 901234567")
        return
    await after_phone_saved(message, state, phone)


@router.message(AnnouncementStates.car_model, F.text)
@router.message(DriverAutoStates.waiting_car_type, F.text)
async def car_model_handler(message: Message, state: FSMContext) -> None:
    car_model = message.text.strip()
    if len(car_model) < 2:
        await message.answer("Mashina turini to'liqroq kiriting. Masalan: Cobalt")
        return
    await state.update_data(car_model=car_model)
    current_state = await state.get_state()
    if current_state == DriverAutoStates.waiting_car_type.state:
        await state.set_state(DriverAutoStates.waiting_photo)
        await message.answer("3️⃣ Mashina rasmini yuboring:", reply_markup=cancel_keyboard())
        return
    await state.set_state(AnnouncementStates.car_photo)
    await message.answer("📷 Mashina rasmini yuboring yoki o'tkazib yuboring:", reply_markup=skip_photo_keyboard())


@router.message(DriverAutoStates.waiting_car_type)
async def driver_auto_wrong_car_model_handler(message: Message) -> None:
    await message.answer("Mashina turini text ko'rinishida kiriting. Masalan: Cobalt")


@router.message(DriverAutoStates.waiting_photo, F.photo)
async def driver_auto_photo_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(car_photo_file_id=message.photo[-1].file_id)
    await state.set_state(DriverAutoStates.waiting_direction)
    await message.answer("✅ Rasm qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await message.answer("4️⃣ Yo'nalishni tanlang:", reply_markup=driver_auto_direction_keyboard())


@router.message(DriverAutoStates.waiting_photo)
async def driver_auto_wrong_photo_handler(message: Message) -> None:
    await message.answer("Mashina rasmini yuboring:", reply_markup=cancel_keyboard())


@router.message(AnnouncementStates.car_photo, F.photo)
async def car_photo_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(car_photo_file_id=message.photo[-1].file_id)
    await state.set_state(AnnouncementStates.route)
    await message.answer("✅ Rasm qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await ask_route(message)


@router.message(AnnouncementStates.car_photo, F.text.in_({"⏭️ O'tkazib yuborish", "O'tkazib yuborish"}))
async def skip_photo_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(car_photo_file_id=None)
    await state.set_state(AnnouncementStates.route)
    await message.answer("⏭️ Rasm o'tkazib yuborildi.", reply_markup=ReplyKeyboardRemove())
    await ask_route(message)


@router.message(AnnouncementStates.car_photo)
async def wrong_photo_handler(message: Message) -> None:
    await message.answer("Rasm yuboring yoki \"⏭️ O'tkazib yuborish\" tugmasini bosing.")


@router.callback_query(DriverAutoStates.waiting_direction, F.data.startswith("driver_auto_direction:"))
async def driver_auto_direction_callback(callback: CallbackQuery, state: FSMContext) -> None:
    route_slug = callback.data.split(":", 1)[1]
    direction = driver_auto_direction(route_slug)
    if not direction:
        await callback.answer("Yo'nalish topilmadi.", show_alert=True)
        return
    await state.update_data(**direction)
    await state.set_state(DriverAutoStates.waiting_seat)
    logger.info("driver auto direction selected", user_id=callback.from_user.id, route_slug=route_slug)
    await callback.message.answer("5️⃣ Bo'sh joy sonini tanlang:", reply_markup=seats_keyboard())
    await callback.answer()


@router.message(DriverAutoStates.waiting_direction)
async def driver_auto_direction_text_blocker(message: Message) -> None:
    await message.answer("Yo'nalishni tugma orqali tanlang:", reply_markup=driver_auto_direction_keyboard())


@router.callback_query(AnnouncementStates.route, F.data.startswith("route:"))
async def route_callback(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.split(":", 1)[1]
    try:
        route = await get_route(slug)
    except Route.DoesNotExist:
        await callback.answer("Bu yo'nalish hozir aktiv emas.", show_alert=True)
        return
    await state.update_data(route_slug=route.slug, route_title=route_title_for_model(route), target_route_slugs=[route.slug])
    data = await state.get_data()
    logger.info("route selected", user_id=callback.from_user.id, route=slug)
    if data["announcement_type"] == Announcement.Type.DRIVER:
        await state.set_state(AnnouncementStates.seats)
        await callback.message.answer("💺 Bo'sh joy sonini tanlang:", reply_markup=seats_keyboard())
    else:
        await state.set_state(AnnouncementStates.people_count)
        await callback.message.answer("👥 Necha kishi?", reply_markup=people_count_keyboard())
    await callback.answer()


@router.callback_query(AnnouncementStates.seats, F.data.in_(set(SEAT_VALUES)))
@router.callback_query(DriverAutoStates.waiting_seat, F.data.in_(set(SEAT_VALUES)))
async def seats_callback(callback: CallbackQuery, state: FSMContext) -> None:
    seats = SEAT_VALUES[callback.data]
    await state.update_data(seats=seats)
    current_state = await state.get_state()
    is_driver_auto = current_state == DriverAutoStates.waiting_seat.state
    await state.set_state(DriverAutoStates.waiting_time if is_driver_auto else AnnouncementStates.departure_time)
    await callback.message.answer(f"✅ Tanlandi: {seats} joy")
    prefix = "driver_auto_time" if is_driver_auto else "driver_time"
    await callback.message.answer("6️⃣ Jo'nash vaqtini tanlang:", reply_markup=time_keyboard(prefix))
    await callback.answer()


@router.message(AnnouncementStates.seats)
@router.message(DriverAutoStates.waiting_seat)
async def seats_text_blocker(message: Message) -> None:
    await message.answer("Bo'sh joy sonini tugmalar orqali tanlang:", reply_markup=seats_keyboard())


@router.callback_query(AnnouncementStates.people_count, F.data.in_(set(PEOPLE_VALUES)))
async def people_count_callback(callback: CallbackQuery, state: FSMContext) -> None:
    people_count = PEOPLE_VALUES[callback.data]
    await state.update_data(people_count=people_count)
    await state.set_state(AnnouncementStates.gender)
    await callback.message.answer(f"✅ Tanlandi: {people_count}")
    await callback.message.answer("👤 Kim ketadi?", reply_markup=gender_keyboard())
    await callback.answer()


@router.message(AnnouncementStates.people_count)
async def people_count_text_blocker(message: Message) -> None:
    await message.answer("Kishi sonini tugmalar orqali tanlang:", reply_markup=people_count_keyboard())


@router.callback_query(AnnouncementStates.gender, F.data.in_(set(GENDER_VALUES)))
async def gender_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(gender=GENDER_VALUES[callback.data])
    await state.set_state(AnnouncementStates.baggage)
    await callback.message.answer("🎒 Bagaj bormi?", reply_markup=baggage_keyboard())
    await callback.answer()


@router.message(AnnouncementStates.gender)
async def gender_text_blocker(message: Message) -> None:
    await message.answer("Jinsni tugma orqali tanlang:", reply_markup=gender_keyboard())


@router.callback_query(AnnouncementStates.baggage, F.data.in_(set(BAGGAGE_VALUES)))
async def baggage_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(baggage=BAGGAGE_VALUES[callback.data])
    await state.set_state(AnnouncementStates.departure_time)
    await callback.message.answer("🕒 Vaqtni tanlang:", reply_markup=time_keyboard("passenger_time"))
    await callback.answer()


@router.message(AnnouncementStates.baggage)
async def baggage_text_blocker(message: Message) -> None:
    await message.answer("Bagaj holatini tugma orqali tanlang:", reply_markup=baggage_keyboard())


def parse_hour(callback_data: str, prefix: str) -> int | None:
    raw_hour = callback_data.removeprefix(f"{prefix}_")
    if not raw_hour.isdigit():
        return None
    hour = int(raw_hour)
    if hour not in range(24):
        return None
    return hour


async def handle_time_selection(
    callback: CallbackQuery,
    state: FSMContext,
    prefix: str,
    repeat_state=AnnouncementStates.repeat_interval,
) -> None:
    hour = parse_hour(callback.data, prefix)
    if hour is None:
        await callback.answer("Vaqt noto'g'ri.", show_alert=True)
        return
    selected_time = f"{hour:02d}:00"
    await state.update_data(departure_time=selected_time)
    await state.set_state(repeat_state)
    await callback.message.answer(f"✅ Tanlandi: {selected_time}")
    await ask_repeat_interval(callback.message)
    await callback.answer()


@router.callback_query(AnnouncementStates.departure_time, F.data.startswith("driver_time_"))
async def driver_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_time_selection(callback, state, "driver_time")


@router.callback_query(DriverAutoStates.waiting_time, F.data.startswith("driver_auto_time_"))
async def driver_auto_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_time_selection(callback, state, "driver_auto_time", DriverAutoStates.waiting_interval)


@router.callback_query(AnnouncementStates.departure_time, F.data.startswith("passenger_time_"))
async def passenger_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_time_selection(callback, state, "passenger_time")


@router.message(AnnouncementStates.departure_time)
async def departure_time_text_blocker(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prefix = "driver_time" if data.get("announcement_type") == Announcement.Type.DRIVER else "passenger_time"
    await message.answer("Vaqtni tugmalar orqali tanlang:", reply_markup=time_keyboard(prefix))


@router.message(DriverAutoStates.waiting_time)
async def driver_auto_time_text_blocker(message: Message) -> None:
    await message.answer("Vaqtni tugmalar orqali tanlang:", reply_markup=time_keyboard("driver_auto_time"))


@router.callback_query(AnnouncementStates.repeat_interval, F.data.startswith("repeat_interval:"))
@router.callback_query(DriverManualStates.waiting_interval, F.data.startswith("repeat_interval:"))
@router.callback_query(DriverAutoStates.waiting_interval, F.data.startswith("repeat_interval:"))
async def repeat_interval_callback(callback: CallbackQuery, state: FSMContext) -> None:
    raw_minutes = callback.data.split(":", 1)[1]
    if not raw_minutes.isdigit():
        await callback.answer("Interval noto'g'ri.", show_alert=True)
        return
    minutes = int(raw_minutes)
    if minutes not in {0, 2, 5, 10}:
        await callback.answer("Interval noto'g'ri.", show_alert=True)
        return
    await state.update_data(repeat_interval_minutes=minutes)
    current_state = await state.get_state()
    data = await state.get_data()
    logger.info("repeat selected", user_id=callback.from_user.id, interval=minutes)
    if current_state == DriverManualStates.waiting_interval.state:
        await state.set_state(DriverManualStates.confirm)
    elif current_state == DriverAutoStates.waiting_interval.state:
        await state.set_state(DriverAutoStates.confirm)
    else:
        await state.set_state(AnnouncementStates.preview)
    await send_preview(callback.message, data)
    await callback.answer()


@router.message(DriverManualStates.waiting_interval)
@router.message(DriverAutoStates.waiting_interval)
async def repeat_interval_text_blocker(message: Message) -> None:
    await message.answer("Qayta yuborish intervalini tugma orqali tanlang:", reply_markup=repeat_interval_keyboard())


@router.callback_query(AnnouncementStates.preview, F.data == "announcement_confirm")
@router.callback_query(DriverManualStates.confirm, F.data == "announcement_confirm")
@router.callback_query(DriverAutoStates.confirm, F.data == "announcement_confirm")
async def confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info("confirm clicked", user_id=callback.from_user.id)
    data = await state.get_data()
    try:
        announcement, debug, allowed, wait_seconds = await create_announcement(data, callback.from_user.id)
    except Route.DoesNotExist:
        await callback.message.answer(
            "Route topilmadi. Admin panelda route'larni tekshiring yoki `python manage.py seed_routes` ishga tushiring.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return
    logger.info("announcement created", announcement_id=announcement.id, target_count=debug["target_count"])
    if not allowed:
        await callback.message.answer(
            f"Yangi e'lon berish uchun {humanize_seconds(wait_seconds)} kuting.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return
    if debug["target_count"] == 0:
        await callback.message.answer(
            "E'lon bazaga yozildi, lekin yuborilmadi.\n"
            "Sabab: Bu route hali hech qaysi active admin guruhga ulanmagan.\n\n"
            f"route slug: {debug['route_slug']}\n"
            f"route title: {debug['route_title']}\n"
            f"target route slugs: {', '.join(debug.get('target_route_slugs', []))}\n"
            f"shu routega ulangan jami group count: {debug['total_groups_for_route']}\n"
            f"active group count: {debug['active_groups_for_route']}\n"
            f"bot_is_admin count: {debug['bot_admin_groups_for_route']}",
            reply_markup=main_menu_keyboard(),
        )
    else:
        send_announcement_task.delay(announcement.id, False)
        await callback.message.answer(
            f"E'lon qabul qilindi. Target group count: {debug['target_count']}.\n"
            "Yuborish boshlandi, katta guruhlarda flood limitdan saqlanish uchun xabarlar navbat bilan ketadi.",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "announcement_cancel")
async def announcement_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("E'lon bekor qilindi.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "announcement_restart")
async def announcement_restart_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Qayta boshlaymiz. Rolni tanlang:", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("stop_announcement:"))
async def stop_announcement_callback(callback: CallbackQuery) -> None:
    announcement_id = int(callback.data.split(":", 1)[1])
    stopped = await stop_announcement(announcement_id, callback.from_user.id)
    if stopped:
        await callback.message.answer("E'lon to'xtatildi.", reply_markup=main_menu_keyboard())
    else:
        await callback.message.answer("Bu e'lon topilmadi yoki allaqachon to'xtatilgan.")
    await callback.answer()


@router.callback_query()
async def unhandled_callback(callback: CallbackQuery) -> None:
    logger.warning("unhandled callback", user_id=callback.from_user.id, data=callback.data)
    await callback.answer("Bu tugma uchun amal topilmadi. /start ni bosing.", show_alert=True)
