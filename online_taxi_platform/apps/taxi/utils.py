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


def format_announcement(announcement: Announcement) -> str:
    note = announcement.note or "Yo'q"
    baggage = announcement.baggage or "Yo'q"
    if announcement.announcement_type == Announcement.Type.DRIVER:
        return (
            "🚖 HAYDOVCHI E'LONI\n\n"
            f"📍 Yo'nalish: {announcement.route.name}\n"
            f"🕒 Jo'nash vaqti: {announcement.departure_time}\n"
            f"💺 Bo'sh joy: {announcement.seats or '-'}\n"
            f"💰 Narx: {announcement.price or 'Kelishiladi'}\n"
            f"🚘 Mashina: {announcement.car_model or '-'}\n"
            f"🔢 Raqam: {announcement.car_number or '-'}\n"
            f"👤 Haydovchi: {announcement.full_name}\n"
            f"📞 Telefon: {announcement.phone}\n"
            f"📝 Izoh: {note}\n\n"
            f"🔁 Qayta yuborish: {repeat_label(announcement.repeat_interval_minutes)}"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {announcement.route.name}\n"
        f"👥 Kishi soni: {announcement.people_count or '-'}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {announcement.departure_time}\n"
        f"👤 Ism: {announcement.full_name}\n"
        f"📞 Telefon: {announcement.phone}\n"
        f"📝 Izoh: {note}\n\n"
        f"🔁 Qayta yuborish: {repeat_label(announcement.repeat_interval_minutes)}"
    )


def build_preview(data: dict, route_name: str) -> str:
    note = data.get("note") or "Yo'q"
    baggage = data.get("baggage") or "Yo'q"
    repeat = repeat_label(int(data.get("repeat_interval_minutes", 0)))
    if data["announcement_type"] == Announcement.Type.DRIVER:
        return (
            "🚖 HAYDOVCHI E'LONI\n\n"
            f"📍 Yo'nalish: {route_name}\n"
            f"🕒 Jo'nash vaqti: {data.get('departure_time')}\n"
            f"💺 Bo'sh joy: {data.get('seats')}\n"
            f"💰 Narx: {data.get('price') or 'Kelishiladi'}\n"
            f"🚘 Mashina: {data.get('car_model')}\n"
            f"🔢 Raqam: {data.get('car_number')}\n"
            f"👤 Haydovchi: {data.get('full_name')}\n"
            f"📞 Telefon: {data.get('phone')}\n"
            f"📝 Izoh: {note}\n\n"
            f"🔁 Qayta yuborish: {repeat}"
        )
    return (
        "🙋 YO'LOVCHI E'LONI\n\n"
        f"📍 Yo'nalish: {route_name}\n"
        f"👥 Kishi soni: {data.get('people_count')}\n"
        f"🎒 Bagaj: {baggage}\n"
        f"🕒 Vaqt: {data.get('departure_time')}\n"
        f"👤 Ism: {data.get('full_name')}\n"
        f"📞 Telefon: {data.get('phone')}\n"
        f"📝 Izoh: {note}\n\n"
        f"🔁 Qayta yuborish: {repeat}"
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
