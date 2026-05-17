from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import Announcement


def repeat_label(minutes: int) -> str:
    labels = {
        0: "Bir marta",
        2: "Har 2 minutda",
        5: "Har 5 minutda",
        10: "Har 10 minutda",
    }
    return labels.get(minutes, f"Har {minutes} minutda")


def gender_label(value: str | None) -> str:
    labels = {
        Announcement.Gender.MALE: "Erkak",
        Announcement.Gender.FEMALE: "Ayol",
    }
    return labels.get(value, "-")


def clean_route_title(route_title: str | None) -> str:
    return (route_title or "").strip() or "-"


def format_announcement(announcement: Announcement) -> str:
    baggage = announcement.baggage or "Yo'q"
    route_title = clean_route_title(announcement.route_title)
    if announcement.announcement_type == Announcement.Type.DRIVER:
        if announcement.mode == Announcement.Mode.MANUAL:
            return (announcement.note or "").strip()
        return (
            "━━━━━━━━━━━━━━\n"
            "🚖 HAYDOVCHI E'LONI\n\n"
            "📍 Yo'nalish:\n"
            f"{route_title}\n\n"
            f"🪑 Bo'sh joy: {announcement.seats or '-'} ta\n\n"
            f"🕓 Vaqt: {announcement.departure_time}\n\n"
            "🚘 Mashina:\n"
            f"{announcement.car_model or '-'}\n\n"
            "📞 Telefon:\n"
            f"{announcement.phone}\n"
            "━━━━━━━━━━━━━━"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {route_title}\n"
        f"👥 Kishi soni: {announcement.people_count or '-'}\n"
        f"👤 Jins: {gender_label(announcement.gender)}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {announcement.departure_time}\n"
        f"👤 Ism: {announcement.full_name}\n"
        f"📞 Telefon: {announcement.phone}"
    )


def build_preview(data: dict, route_title: str) -> str:
    baggage = data.get("baggage") or "Yo'q"
    interval = repeat_label(int(data.get("repeat_interval_minutes", 0)))
    route_title = clean_route_title(route_title)
    if data.get("mode") == Announcement.Mode.MANUAL:
        return (
            "📝 E'LON QO'LDA\n\n"
            f"{data.get('manual_text', '').strip()}\n\n"
            "━━━━━━━━━━━━━━\n"
            f"🔁 Qayta yuborish: {interval}"
        )
    if data["announcement_type"] == Announcement.Type.DRIVER:
        return (
            "━━━━━━━━━━━━━━\n"
            "🚖 HAYDOVCHI E'LONI\n\n"
            "📍 Yo'nalish:\n"
            f"{route_title}\n\n"
            f"🪑 Bo'sh joy: {data.get('seats')} ta\n\n"
            f"🕓 Vaqt: {data.get('departure_time')}\n\n"
            "🚘 Mashina:\n"
            f"{data.get('car_model')}\n\n"
            "📞 Telefon:\n"
            f"{data.get('phone')}\n\n"
            f"🔁 Qayta yuborish: {interval}\n"
            "━━━━━━━━━━━━━━"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {route_title}\n"
        f"👥 Kishi soni: {data.get('people_count')}\n"
        f"👤 Jins: {gender_label(data.get('gender'))}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {data.get('departure_time')}\n"
        f"👤 Ism: {data.get('full_name')}\n"
        f"📞 Telefon: {data.get('phone')}\n"
        f"🔁 Qayta yuborish: {interval}"
    )


def next_repeat_time(minutes: int):
    if minutes <= 0:
        return None
    return timezone.now() + timedelta(minutes=minutes)


def repeat_until(hours: int):
    return timezone.now() + timedelta(hours=hours)


def humanize_seconds(seconds: int) -> str:
    minutes, rest = divmod(max(seconds, 0), 60)
    if minutes:
        return f"{minutes} minut {rest} sekund"
    return f"{rest} sekund"
