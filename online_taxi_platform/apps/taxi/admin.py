from django.contrib import admin
from django.db.models import Count, Q

from .models import Announcement, Blacklist, DeliveryLog, Route, TelegramGroup, TelegramUser


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "from_city", "to_city", "is_active", "active_group_count", "created_at")
    list_filter = ("is_active", "from_city", "to_city")
    search_fields = ("name", "slug", "from_city", "to_city")
    prepopulated_fields = {"slug": ("from_city", "to_city")}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            active_groups=Count(
                "telegram_groups",
                filter=Q(telegram_groups__is_active=True, telegram_groups__bot_is_admin=True),
                distinct=True,
            )
        )

    @admin.display(description="Active groups")
    def active_group_count(self, obj):
        return obj.active_groups


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("full_name", "telegram_id", "phone", "role", "is_vip", "is_blocked", "updated_at")
    list_filter = ("role", "is_vip", "is_blocked")
    search_fields = ("full_name", "phone", "telegram_id")


@admin.register(TelegramGroup)
class TelegramGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "chat_id", "is_active", "bot_is_admin", "route_count", "updated_at")
    list_filter = ("is_active", "bot_is_admin", "chat_type", "is_forum")
    search_fields = ("title", "username", "chat_id")
    filter_horizontal = ("routes",)

    @admin.display(description="Routes")
    def route_count(self, obj):
        return obj.routes.count()


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "announcement_type",
        "route",
        "user",
        "status",
        "repeat_interval_minutes",
        "send_count",
        "created_at",
    )
    list_filter = ("announcement_type", "status", "is_repeating", "route")
    search_fields = ("full_name", "phone", "car_model", "car_number", "note")
    readonly_fields = ("created_at", "updated_at", "send_count")


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("status", "group", "announcement", "is_repeated", "telegram_message_id", "sent_at")
    list_filter = ("status", "is_repeated", "group")
    search_fields = ("error_message", "group__title", "announcement__full_name")


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "reason", "created_at")
    search_fields = ("telegram_id", "reason")
