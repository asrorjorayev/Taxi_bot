from __future__ import annotations

import asyncio
import os
import random

import django
from asgiref.sync import sync_to_async
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from constants.routes import DRIVER_MANUAL_TARGET_SLUGS  # noqa: E402
from .models import Announcement, DeliveryLog, Route, TelegramGroup, TelegramUser  # noqa: E402
from .log import get_logger  # noqa: E402
from .utils import format_announcement, next_repeat_time, repeat_until  # noqa: E402
from utils.route_formatter import (  # noqa: E402
    primary_db_slug_for_route,
    route_payload,
    route_title_for_model,
    route_title_for_slug,
    target_slugs_for_route,
)

logger = get_logger(__name__)

TELEGRAM_PHOTO_CAPTION_LIMIT = 1024
TELEGRAM_MESSAGE_LIMIT = 4096


def driver_auto_direction(route_slug: str) -> dict | None:
    return route_payload(route_slug)


def announcement_target_slugs(announcement: Announcement) -> list[str]:
    slugs = announcement.target_route_slugs or []
    return (
        list(dict.fromkeys(slug for slug in slugs if slug))
        or target_slugs_for_route(announcement.route_slug)
        or [announcement.route.slug]
    )


def target_groups_queryset(announcement: Announcement):
    target_slugs = announcement_target_slugs(announcement)
    return TelegramGroup.objects.filter(
        routes__slug__in=target_slugs,
        is_active=True,
        bot_is_admin=True,
    ).distinct()


def get_target_group_debug(announcement: Announcement) -> dict:
    target_slugs = announcement_target_slugs(announcement)
    total_for_route = TelegramGroup.objects.filter(routes__slug__in=target_slugs).distinct().count()
    active_for_route = TelegramGroup.objects.filter(routes__slug__in=target_slugs, is_active=True).distinct().count()
    bot_admin_for_route = TelegramGroup.objects.filter(
        routes__slug__in=target_slugs,
        bot_is_admin=True,
    ).distinct().count()
    target_count = target_groups_queryset(announcement).count()
    return {
        "route_slug": announcement.route_slug,
        "route_title": announcement.route_title,
        "target_route_slugs": target_slugs,
        "target_count": target_count,
        "total_groups_for_route": total_for_route,
        "active_groups_for_route": active_for_route,
        "bot_admin_groups_for_route": bot_admin_for_route,
    }


def route_group_stats() -> list[dict]:
    from .models import Route

    routes = Route.objects.annotate(
        total_groups=Count("telegram_groups", distinct=True),
        active_groups=Count("telegram_groups", filter=Q(telegram_groups__is_active=True), distinct=True),
        bot_admin_groups=Count("telegram_groups", filter=Q(telegram_groups__bot_is_admin=True), distinct=True),
    ).order_by("name")
    return [
        {
            "title": route_title_for_model(route),
            "slug": route.slug,
            "total_groups": route.total_groups,
            "active_groups": route.active_groups,
            "bot_admin_groups": route.bot_admin_groups,
        }
        for route in routes
    ]


def user_can_create_announcement(user) -> tuple[bool, int]:
    if user.role == user.Role.ADMIN:
        return True, 0
    cooldown = 120 if user.is_vip else 600
    last = (
        Announcement.objects.filter(user=user)
        .exclude(status=Announcement.Status.DRAFT)
        .order_by("-created_at")
        .first()
    )
    if not last:
        return True, 0
    elapsed = int((timezone.now() - last.created_at).total_seconds())
    if elapsed >= cooldown:
        return True, 0
    return False, cooldown - elapsed


def create_announcement_from_data(data: dict, telegram_id: int) -> tuple[Announcement, dict, bool, int]:
    user = TelegramUser.objects.get(telegram_id=telegram_id)
    allowed, wait_seconds = user_can_create_announcement(user)
    route_slug = data["route_slug"]
    route = Route.objects.get(slug=primary_db_slug_for_route(route_slug))
    route_title = data.get("route_title") or route_title_for_slug(route_slug, route_title_for_model(route))
    interval = int(data.get("repeat_interval_minutes", 0))
    target_route_slugs = data.get("target_route_slugs") or target_slugs_for_route(route_slug) or [route.slug]
    announcement = Announcement.objects.create(
        user=user,
        announcement_type=data["announcement_type"],
        mode=data.get("mode", Announcement.Mode.AUTO),
        route=route,
        route_slug=route_slug,
        route_title=route_title,
        target_route_slugs=list(dict.fromkeys(target_route_slugs)),
        full_name=data.get("full_name") or user.full_name,
        phone=data.get("phone") or user.phone or "-",
        car_model=data.get("car_model"),
        car_number=None,
        car_photo_file_id=data.get("car_photo_file_id"),
        seats=data.get("seats"),
        people_count=data.get("people_count"),
        gender=data.get("gender"),
        baggage=data.get("baggage"),
        departure_time=data.get("departure_time") or "-",
        price=None,
        note=data.get("manual_text") or data.get("note"),
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


def _split_telegram_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
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


async def _send_media_or_text(bot: Bot, group: TelegramGroup, photo_file_id: str | None, text: str):
    if photo_file_id and len(text) <= TELEGRAM_PHOTO_CAPTION_LIMIT:
        return await bot.send_photo(group.chat_id, photo_file_id, caption=text)
    if photo_file_id:
        first_message = await bot.send_photo(group.chat_id, photo_file_id)
        for chunk in _split_telegram_text(text):
            await bot.send_message(group.chat_id, chunk)
        return first_message

    first_message = None
    for chunk in _split_telegram_text(text):
        sent_message = await bot.send_message(group.chat_id, chunk)
        if first_message is None:
            first_message = sent_message
    return first_message


async def _send_one(bot: Bot, announcement: Announcement, group: TelegramGroup, is_repeated: bool) -> None:
    log = await sync_to_async(DeliveryLog.objects.create)(
        announcement=announcement,
        group=group,
        is_repeated=is_repeated,
        status=DeliveryLog.Status.PENDING,
    )
    text = format_announcement(announcement)
    try:
        message = await _send_media_or_text(bot, group, announcement.car_photo_file_id, text)
        now = timezone.now()
        log.status = DeliveryLog.Status.SUCCESS
        log.telegram_message_id = message.message_id
        log.sent_at = now
        await sync_to_async(log.save)(update_fields=["status", "telegram_message_id", "sent_at"])
        group.last_successful_delivery = now
        await sync_to_async(group.save)(update_fields=["last_successful_delivery"])
        logger.info("delivery success", announcement_id=announcement.id, group_id=group.id, repeated=is_repeated)
    except TelegramRetryAfter as exc:
        logger.warning("telegram retry after", retry_after=exc.retry_after, group_id=group.id)
        await asyncio.sleep(exc.retry_after + 1)
        raise
    except TelegramForbiddenError as exc:
        group.is_active = False
        group.last_failed_delivery = timezone.now()
        await sync_to_async(group.save)(update_fields=["is_active", "last_failed_delivery"])
        log.status = DeliveryLog.Status.FAILED
        log.error_message = str(exc)
        await sync_to_async(log.save)(update_fields=["status", "error_message"])
        logger.warning("delivery failed forbidden", group_id=group.id, error=str(exc))
    except (TelegramBadRequest, TelegramNetworkError) as exc:
        group.last_failed_delivery = timezone.now()
        await sync_to_async(group.save)(update_fields=["last_failed_delivery"])
        log.status = DeliveryLog.Status.FAILED
        log.error_message = str(exc)
        await sync_to_async(log.save)(update_fields=["status", "error_message"])
        logger.warning("delivery failed", group_id=group.id, error=str(exc))


async def async_send_announcement_now(announcement_id: int, is_repeated: bool = False) -> dict:
    announcement = await sync_to_async(
        Announcement.objects.select_related("route", "user").get
    )(id=announcement_id)
    groups = await sync_to_async(list)(target_groups_queryset(announcement))
    logger.info("target group count", announcement_id=announcement_id, count=len(groups))
    if not groups:
        return {"sent": 0, "failed": 0, "debug": await sync_to_async(get_target_group_debug)(announcement)}

    bot = Bot(token=settings.BOT_TOKEN)
    sent = 0
    failed = 0
    try:
        for group in groups:
            try:
                await _send_one(bot, announcement, group, is_repeated)
                sent += 1
            except Exception as exc:
                failed += 1
                logger.warning("delivery failed unexpected", group_id=group.id, error=str(exc))
            await asyncio.sleep(random.uniform(1, 3))
    finally:
        await bot.session.close()

    announcement.status = Announcement.Status.SENT if sent else Announcement.Status.FAILED
    announcement.send_count += sent
    await sync_to_async(announcement.save)(update_fields=["status", "send_count", "updated_at"])
    return {"sent": sent, "failed": failed, "debug": None}


def send_announcement_now(announcement_id: int, is_repeated: bool = False) -> dict:
    return asyncio.run(async_send_announcement_now(announcement_id, is_repeated=is_repeated))
