from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚖 Haydovchi"), KeyboardButton(text="🙋 Yo'lovchi")],
            [KeyboardButton(text="📋 Faol e'lonlarim"), KeyboardButton(text="ℹ️ Yordam")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Telefon yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_photo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭️ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def routes_keyboard(routes) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for route in routes:
        builder.button(text=f"📍 {route.name}", callback_data=f"route:{route.slug}")
    builder.adjust(1)
    return builder.as_markup()


def seats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣", callback_data="seat_1"),
                InlineKeyboardButton(text="2️⃣", callback_data="seat_2"),
            ],
            [
                InlineKeyboardButton(text="3️⃣", callback_data="seat_3"),
                InlineKeyboardButton(text="4️⃣", callback_data="seat_4"),
            ],
        ]
    )


def people_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣", callback_data="people_1"),
                InlineKeyboardButton(text="2️⃣", callback_data="people_2"),
            ],
            [
                InlineKeyboardButton(text="3️⃣", callback_data="people_3"),
                InlineKeyboardButton(text="4️⃣", callback_data="people_4"),
            ],
            [InlineKeyboardButton(text="📦 Pochta", callback_data="people_post")],
        ]
    )


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Erkak", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Ayol", callback_data="gender_female"),
            ]
        ]
    )


def baggage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Bor", callback_data="baggage_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="baggage_no"),
            ]
        ]
    )


def time_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hour in range(24):
        builder.button(text=f"{hour:02d}:00", callback_data=f"{prefix}_{hour:02d}")
    builder.adjust(2)
    return builder.as_markup()


def repeat_interval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Bir marta", callback_data="repeat_interval:0")],
            [InlineKeyboardButton(text="🔁 Har 2 minutda", callback_data="repeat_interval:2")],
            [InlineKeyboardButton(text="🔁 Har 5 minutda", callback_data="repeat_interval:5")],
            [InlineKeyboardButton(text="🔁 Har 10 minutda", callback_data="repeat_interval:10")],
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="announcement_confirm")],
            [InlineKeyboardButton(text="✏️ Qayta to'ldirish", callback_data="announcement_restart")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="announcement_cancel")],
        ]
    )


def group_routes_keyboard(routes, selected_slugs: set[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for route in routes:
        mark = "✅" if route.slug in selected_slugs else "⬜"
        builder.button(text=f"{mark} {route.name}", callback_data=f"group_route_toggle:{route.slug}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="✅ Saqlash", callback_data="group_route_save"))
    return builder.as_markup()


def active_announcements_keyboard(announcements) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in announcements:
        builder.button(text=f"⏹️ To'xtatish #{item.id}", callback_data=f"stop_announcement:{item.id}")
    builder.adjust(1)
    return builder.as_markup()
