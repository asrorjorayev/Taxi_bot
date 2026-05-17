from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from constants.routes import DRIVER_AUTO_ROUTE_SLUGS
from utils.route_formatter import route_title_for_model, route_title_for_slug


def routes_keyboard(routes) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for route in routes:
        builder.button(text=route_title_for_model(route), callback_data=f"route:{route.slug}")
    builder.adjust(1)
    return builder.as_markup()


def driver_auto_direction_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=route_title_for_slug(slug),
                    callback_data=f"driver_auto_direction:{slug}",
                )
            ]
            for slug in DRIVER_AUTO_ROUTE_SLUGS
        ]
    )


def group_routes_keyboard(routes, selected_slugs: set[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for route in routes:
        mark = "✅" if route.slug in selected_slugs else "⬜"
        builder.button(text=f"{mark} {route_title_for_model(route)}", callback_data=f"group_route_toggle:{route.slug}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="✅ Saqlash", callback_data="group_route_save"))
    return builder.as_markup()
