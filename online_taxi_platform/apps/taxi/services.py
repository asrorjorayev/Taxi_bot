from __future__ import annotations

import asyncio
import os
import random

import django
from asgiref.sync import sync_to_async
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from django.db.models import Count, Q
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from .models import Announcement, DeliveryLog, TelegramGroup  # noqa: E402
from .log import get_logger  # noqa: E402
from .utils import format_announcement  # noqa: E402

logger = get_logger(__name__)


def target_groups_queryset(announcement: Announcement):
    return TelegramGroup.objects.filter(
        routes=announcement.route,
        is_active=True,
        bot_is_admin=True,
    ).distinct()


def get_target_group_debug(announcement: Announcement) -> dict:
    total_for_route = TelegramGroup.objects.filter(routes=announcement.route).distinct().count()
    active_for_route = TelegramGroup.objects.filter(routes=announcement.route, is_active=True).distinct().count()
    bot_admin_for_route = TelegramGroup.objects.filter(routes=announcement.route, bot_is_admin=True).distinct().count()
    target_count = target_groups_queryset(announcement).count()
    return {
        "route_slug": announcement.route.slug,
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
            "name": route.name,
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


async def _send_one(bot: Bot, announcement: Announcement, group: TelegramGroup, is_repeated: bool) -> None:
    log = await sync_to_async(DeliveryLog.objects.create)(
        announcement=announcement,
        group=group,
        is_repeated=is_repeated,
        status=DeliveryLog.Status.PENDING,
    )
    text = format_announcement(announcement)
    try:
        if announcement.car_photo_file_id:
            message = await bot.send_photo(group.chat_id, announcement.car_photo_file_id, caption=text)
        else:
            message = await bot.send_message(group.chat_id, text)
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
    from django.conf import settings

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
