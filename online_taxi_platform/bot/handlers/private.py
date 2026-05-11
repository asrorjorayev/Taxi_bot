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
from apps.taxi.services import get_target_group_debug, user_can_create_announcement  # noqa: E402
from apps.taxi.tasks import send_announcement_task  # noqa: E402
from apps.taxi.utils import build_preview, humanize_seconds, next_repeat_time, repeat_until  # noqa: E402
from bot.keyboards import (  # noqa: E402
    active_announcements_keyboard,
    baggage_keyboard,
    cancel_keyboard,
    confirm_keyboard,
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
from bot.states import AnnouncementStates  # noqa: E402
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
    user = TelegramUser.objects.get(telegram_id=telegram_id)
    allowed, wait_seconds = user_can_create_announcement(user)
    route = Route.objects.get(slug=data["route_slug"])
    interval = int(data.get("repeat_interval_minutes", 0))
    announcement = Announcement.objects.create(
        user=user,
        announcement_type=data["announcement_type"],
        route=route,
        full_name=data["full_name"],
        phone=data["phone"],
        car_model=data.get("car_model"),
        car_number=None,
        car_photo_file_id=data.get("car_photo_file_id"),
        seats=data.get("seats"),
        people_count=data.get("people_count"),
        gender=data.get("gender"),
        baggage=data.get("baggage"),
        departure_time=data["departure_time"],
        price=None,
        note=None,
        repeat_interval_minutes=interval,
        is_repeating=interval > 0,
        repeat_until=repeat_until(settings.REPEAT_TTL_HOURS) if interval > 0 else None,
        next_send_at=next_repeat_time(interval),
        status=Announcement.Status.QUEUED if allowed else Announcement.Status.DRAFT,
    )
    debug = get_target_group_debug(announcement)
    if not allowed:
        return announcement, debug, False, wait_seconds
    if debug["target_count"] == 0:
        announcement.status = Announcement.Status.FAILED
        announcement.save(update_fields=["status", "updated_at"])
    return announcement, debug, True, 0


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
    await state.set_state(AnnouncementStates.phone)
    logger.info("role selected", user_id=message.from_user.id, role="driver")
    await message.answer("📞 Telefon raqamingizni yuboring yoki yozing:", reply_markup=phone_keyboard())


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
        lines.append(f"#{item.id} - {item.route.name} - {item.get_status_display()}")
    await message.answer("\n".join(lines), reply_markup=active_announcements_keyboard(items))


async def after_phone_saved(message: Message, state: FSMContext, phone: str) -> None:
    data = await state.get_data()
    full_name = data.get("full_name") or telegram_full_name(message)
    await save_user_phone(message.from_user.id, phone, full_name, data["role"])
    await state.update_data(phone=phone, full_name=full_name)
    logger.info("phone received", user_id=message.from_user.id, phone=phone)
    if data["role"] == TelegramUser.Role.DRIVER:
        await state.set_state(AnnouncementStates.car_model)
        await message.answer(
            "🚘 Mashina turini kiriting. Masalan: Cobalt",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_state(AnnouncementStates.route)
    await message.answer("✅ Telefon qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await ask_route(message)


@router.message(AnnouncementStates.phone, F.contact)
async def phone_contact_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        await message.answer("Telefon raqam noto'g'ri. Masalan: +998901234567")
        return
    await after_phone_saved(message, state, phone)


@router.message(AnnouncementStates.phone, F.text)
async def phone_text_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer("Telefon raqam noto'g'ri. Qabul qilinadi: +998901234567, 998901234567, 901234567")
        return
    await after_phone_saved(message, state, phone)


@router.message(AnnouncementStates.car_model, F.text)
async def car_model_handler(message: Message, state: FSMContext) -> None:
    car_model = message.text.strip()
    if len(car_model) < 2:
        await message.answer("Mashina turini to'liqroq kiriting. Masalan: Cobalt")
        return
    await state.update_data(car_model=car_model)
    await state.set_state(AnnouncementStates.car_photo)
    await message.answer("📷 Mashina rasmini yuboring yoki o'tkazib yuboring:", reply_markup=skip_photo_keyboard())


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


@router.callback_query(AnnouncementStates.route, F.data.startswith("route:"))
async def route_callback(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.split(":", 1)[1]
    try:
        route = await get_route(slug)
    except Route.DoesNotExist:
        await callback.answer("Bu yo'nalish hozir aktiv emas.", show_alert=True)
        return
    await state.update_data(route_slug=route.slug, route_name=route.name)
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
async def seats_callback(callback: CallbackQuery, state: FSMContext) -> None:
    seats = SEAT_VALUES[callback.data]
    await state.update_data(seats=seats)
    await state.set_state(AnnouncementStates.departure_time)
    await callback.message.answer(f"✅ Tanlandi: {seats} joy")
    await callback.message.answer("🕒 Jo'nash vaqtini tanlang:", reply_markup=time_keyboard("driver_time"))
    await callback.answer()


@router.message(AnnouncementStates.seats)
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


async def handle_time_selection(callback: CallbackQuery, state: FSMContext, prefix: str) -> None:
    hour = parse_hour(callback.data, prefix)
    if hour is None:
        await callback.answer("Vaqt noto'g'ri.", show_alert=True)
        return
    selected_time = f"{hour:02d}:00"
    await state.update_data(departure_time=selected_time)
    await state.set_state(AnnouncementStates.repeat_interval)
    await callback.message.answer(f"✅ Tanlandi: {selected_time}")
    await ask_repeat_interval(callback.message)
    await callback.answer()


@router.callback_query(AnnouncementStates.departure_time, F.data.startswith("driver_time_"))
async def driver_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_time_selection(callback, state, "driver_time")


@router.callback_query(AnnouncementStates.departure_time, F.data.startswith("passenger_time_"))
async def passenger_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_time_selection(callback, state, "passenger_time")


@router.message(AnnouncementStates.departure_time)
async def departure_time_text_blocker(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prefix = "driver_time" if data.get("announcement_type") == Announcement.Type.DRIVER else "passenger_time"
    await message.answer("Vaqtni tugmalar orqali tanlang:", reply_markup=time_keyboard(prefix))


@router.callback_query(AnnouncementStates.repeat_interval, F.data.startswith("repeat_interval:"))
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
    data = await state.get_data()
    logger.info("repeat selected", user_id=callback.from_user.id, interval=minutes)
    await state.set_state(AnnouncementStates.preview)
    await callback.message.answer(
        build_preview(data, data["route_name"]),
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(AnnouncementStates.preview, F.data == "announcement_confirm")
async def confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info("confirm clicked", user_id=callback.from_user.id)
    data = await state.get_data()
    announcement, debug, allowed, wait_seconds = await create_announcement(data, callback.from_user.id)
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
