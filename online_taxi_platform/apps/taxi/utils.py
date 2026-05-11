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


def format_announcement(announcement: Announcement) -> str:
    baggage = announcement.baggage or "Yo'q"
    if announcement.announcement_type == Announcement.Type.DRIVER:
        return (
            "🚖 HAYDOVCHI E'LONI\n\n"
            f"📍 Yo'nalish: {announcement.route.name}\n"
            f"🕒 Jo'nash vaqti: {announcement.departure_time}\n"
            f"💺 Bo'sh joy: {announcement.seats or '-'}\n"
            f"🚘 Mashina: {announcement.car_model or '-'}\n"
            f"👤 Haydovchi: {announcement.full_name}\n"
            f"📞 Telefon: {announcement.phone}"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {announcement.route.name}\n"
        f"👥 Kishi soni: {announcement.people_count or '-'}\n"
        f"👤 Jins: {gender_label(announcement.gender)}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {announcement.departure_time}\n"
        f"👤 Ism: {announcement.full_name}\n"
        f"📞 Telefon: {announcement.phone}"
    )


def build_preview(data: dict, route_name: str) -> str:
    baggage = data.get("baggage") or "Yo'q"
    if data["announcement_type"] == Announcement.Type.DRIVER:
        return (
            "🚖 HAYDOVCHI E'LONI\n\n"
            f"📍 Yo'nalish: {route_name}\n"
            f"🕒 Jo'nash vaqti: {data.get('departure_time')}\n"
            f"💺 Bo'sh joy: {data.get('seats')}\n"
            f"🚘 Mashina: {data.get('car_model')}\n"
            f"👤 Haydovchi: {data.get('full_name')}\n"
            f"📞 Telefon: {data.get('phone')}"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {route_name}\n"
        f"👥 Kishi soni: {data.get('people_count')}\n"
        f"👤 Jins: {gender_label(data.get('gender'))}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {data.get('departure_time')}\n"
        f"👤 Ism: {data.get('full_name')}\n"
        f"📞 Telefon: {data.get('phone')}"
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
