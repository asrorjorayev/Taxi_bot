from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .log import get_logger
from .models import Announcement
from .services import send_announcement_now

logger = get_logger(__name__)


@shared_task(name="apps.taxi.tasks.send_announcement_task")
def send_announcement_task(announcement_id: int, is_repeated: bool = False) -> dict:
    logger.info("send announcement task started", announcement_id=announcement_id, repeated=is_repeated)
    return send_announcement_now(announcement_id, is_repeated=is_repeated)


@shared_task(name="apps.taxi.tasks.process_repeating_announcements")
def process_repeating_announcements() -> int:
    now = timezone.now()
    logger.info("repeat task started")
    expired = Announcement.objects.filter(
        is_repeating=True,
        repeat_until__lt=now,
    )
    expired_count = expired.update(is_repeating=False, status=Announcement.Status.EXPIRED)

    announcements = list(
        Announcement.objects.filter(
            is_repeating=True,
            next_send_at__lte=now,
            repeat_until__gte=now,
            status__in=[Announcement.Status.SENT, Announcement.Status.QUEUED],
        ).select_related("route", "user")
    )
    logger.info("repeat found count", count=len(announcements), expired=expired_count)
    for announcement in announcements:
        send_announcement_now(announcement.id, is_repeated=True)
        announcement.next_send_at = timezone.now() + timedelta(minutes=announcement.repeat_interval_minutes)
        announcement.save(update_fields=["next_send_at", "updated_at"])
    return len(announcements)
