import os

import django
from asgiref.sync import sync_to_async
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.taxi.models import Route, TelegramGroup  # noqa: E402
from apps.taxi.log import get_logger  # noqa: E402
from apps.taxi.services import route_group_stats  # noqa: E402
from bot.keyboards import group_routes_keyboard  # noqa: E402
from bot.states import GroupRegistrationStates  # noqa: E402

router = Router()
logger = get_logger(__name__)


def is_group_chat(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


async def user_is_chat_admin(message: Message) -> bool:
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def bot_is_chat_admin(message: Message) -> bool:
    me = await message.bot.get_me()
    member = await message.bot.get_chat_member(message.chat.id, me.id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def callback_user_is_admin(callback: CallbackQuery) -> bool:
    member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


@sync_to_async
def get_routes():
    return list(Route.objects.filter(is_active=True).order_by("from_city", "to_city"))


@sync_to_async
def upsert_group(message: Message, bot_is_admin: bool) -> TelegramGroup:
    group, _ = TelegramGroup.objects.update_or_create(
        chat_id=message.chat.id,
        defaults={
            "title": message.chat.title or "No title",
            "username": message.chat.username,
            "chat_type": message.chat.type,
            "is_forum": bool(getattr(message.chat, "is_forum", False)),
            "is_active": True,
            "bot_is_admin": bot_is_admin,
        },
    )
    return group


@sync_to_async
def save_group_routes(chat_id: int, selected_slugs: list[str]) -> int:
    group = TelegramGroup.objects.get(chat_id=chat_id)
    routes = list(Route.objects.filter(slug__in=selected_slugs, is_active=True))
    group.routes.set(routes)
    group.is_active = True
    group.bot_is_admin = True
    group.save(update_fields=["is_active", "bot_is_admin", "updated_at"])
    return len(routes)


@sync_to_async
def get_group_info(chat_id: int) -> dict | None:
    group = TelegramGroup.objects.filter(chat_id=chat_id).prefetch_related("routes").first()
    if not group:
        return None
    routes = list(group.routes.values_list("name", flat=True))
    return {
        "chat_id": group.chat_id,
        "title": group.title,
        "bot_is_admin": group.bot_is_admin,
        "is_active": group.is_active,
        "routes": routes,
        "route_count": len(routes),
    }


@router.message(Command("register_group"))
async def register_group(message: Message, state: FSMContext) -> None:
    if not is_group_chat(message):
        await message.answer("/register_group faqat group yoki supergroup ichida ishlaydi.")
        return
    if not await user_is_chat_admin(message):
        await message.answer("Bu commandni faqat group admin yoki creator ishlata oladi.")
        return
    bot_admin = await bot_is_chat_admin(message)
    await upsert_group(message, bot_admin)
    if not bot_admin:
        await message.answer("Bot bu guruhda admin emas. Avval botni admin qiling, keyin /register_group yuboring.")
        return

    routes = await get_routes()
    if not routes:
        await message.answer("Aktiv route yo'q. Avval admin paneldan route qo'shing yoki seed_routes ishlating.")
        return
    await state.set_state(GroupRegistrationStates.selecting_routes)
    await state.update_data(group_chat_id=message.chat.id, selected_route_slugs=[])
    logger.info("group registration started", chat_id=message.chat.id)
    await message.answer(
        "Bu guruh qaysi yo'nalish e'lonlarini qabul qiladi? Bir nechta route tanlashingiz mumkin:",
        reply_markup=group_routes_keyboard(routes, set()),
    )


@router.callback_query(GroupRegistrationStates.selecting_routes, F.data.startswith("group_route_toggle:"))
async def group_route_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if not await callback_user_is_admin(callback):
        await callback.answer("Faqat group admin tanlay oladi.", show_alert=True)
        return
    slug = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = set(data.get("selected_route_slugs", []))
    if slug in selected:
        selected.remove(slug)
    else:
        selected.add(slug)
    await state.update_data(selected_route_slugs=list(selected))
    routes = await get_routes()
    await callback.message.edit_reply_markup(reply_markup=group_routes_keyboard(routes, selected))
    await callback.answer("Tanlandi")


@router.callback_query(GroupRegistrationStates.selecting_routes, F.data == "group_route_save")
async def group_route_save(callback: CallbackQuery, state: FSMContext) -> None:
    if not await callback_user_is_admin(callback):
        await callback.answer("Faqat group admin saqlay oladi.", show_alert=True)
        return
    data = await state.get_data()
    chat_id = data.get("group_chat_id") or callback.message.chat.id
    selected = data.get("selected_route_slugs", [])
    count = await save_group_routes(chat_id, selected)
    logger.info("group routes saved", chat_id=chat_id, route_count=count)
    await state.clear()
    await callback.message.answer(f"✅ Saqlandi. Bu guruh {count} ta route e'lonlarini qabul qiladi.")
    await callback.answer()


@router.message(Command("debug_group"))
async def debug_group(message: Message) -> None:
    if not is_group_chat(message):
        await message.answer("/debug_group faqat group yoki supergroup ichida ishlaydi.")
        return
    info = await get_group_info(message.chat.id)
    if not info:
        await message.answer("Bu guruh bazada yo'q. /register_group yuboring.")
        return
    await message.answer(
        "DEBUG GROUP\n"
        f"chat_id: {info['chat_id']}\n"
        f"title: {info['title']}\n"
        f"bot_is_admin: {info['bot_is_admin']}\n"
        f"is_active: {info['is_active']}\n"
        f"routes: {', '.join(info['routes']) or '-'}\n"
        f"route count: {info['route_count']}"
    )


@router.message(Command("debug_routes"))
async def debug_routes(message: Message) -> None:
    stats = await sync_to_async(route_group_stats)()
    if not stats:
        await message.answer("Route topilmadi.")
        return
    lines = ["DEBUG ROUTES"]
    for item in stats:
        lines.append(
            f"{item['name']} ({item['slug']}): total={item['total_groups']}, "
            f"active={item['active_groups']}, bot_admin={item['bot_admin_groups']}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("test_send"))
async def test_send(message: Message) -> None:
    if not is_group_chat(message):
        await message.answer("/test_send faqat group yoki supergroup ichida ishlaydi.")
        return
    await message.answer("✅ Test xabar. Bot guruhga xabar yubora olyapti.")
