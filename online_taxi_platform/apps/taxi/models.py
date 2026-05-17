from django.db import models
from django.utils import timezone


class Route(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    from_city = models.CharField(max_length=120)
    to_city = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["from_city", "to_city"]

    def __str__(self) -> str:
        return self.name


class TelegramUser(models.Model):
    class Role(models.TextChoices):
        DRIVER = "driver", "Haydovchi"
        PASSENGER = "passenger", "Yo'lovchi"
        ADMIN = "admin", "Admin"

    telegram_id = models.BigIntegerField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PASSENGER)
    is_blocked = models.BooleanField(default=False)
    is_vip = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.telegram_id})"


class TelegramGroup(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    title = models.CharField(max_length=255)
    username = models.CharField(max_length=255, null=True, blank=True)
    chat_type = models.CharField(max_length=32)
    is_forum = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    bot_is_admin = models.BooleanField(default=False)
    routes = models.ManyToManyField(Route, related_name="telegram_groups", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_successful_delivery = models.DateTimeField(null=True, blank=True)
    last_failed_delivery = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.chat_id})"


class Announcement(models.Model):
    class Type(models.TextChoices):
        DRIVER = "driver", "Haydovchi"
        PASSENGER = "passenger", "Yo'lovchi"

    class Mode(models.TextChoices):
        AUTO = "auto", "Avtomatik"
        MANUAL = "manual", "Qo'lda"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Gender(models.TextChoices):
        MALE = "male", "Erkak"
        FEMALE = "female", "Ayol"

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="announcements")
    announcement_type = models.CharField(max_length=20, choices=Type.choices)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.AUTO)
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="announcements")
    route_slug = models.SlugField(max_length=120, db_index=True, blank=True)
    route_title = models.CharField(max_length=255, blank=True)
    target_route_slugs = models.JSONField(default=list, blank=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    car_model = models.CharField(max_length=120, null=True, blank=True)
    car_number = models.CharField(max_length=50, null=True, blank=True)
    car_photo_file_id = models.CharField(max_length=255, null=True, blank=True)
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    people_count = models.CharField(max_length=20, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True)
    baggage = models.CharField(max_length=255, null=True, blank=True)
    departure_time = models.CharField(max_length=120)
    price = models.CharField(max_length=120, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    repeat_interval_minutes = models.PositiveSmallIntegerField(default=0)
    is_repeating = models.BooleanField(default=False)
    repeat_until = models.DateTimeField(null=True, blank=True)
    next_send_at = models.DateTimeField(null=True, blank=True)
    send_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "is_repeating", "next_send_at"], name="taxi_ann_status_repeat_idx"),
            models.Index(fields=["user", "created_at"], name="taxi_ann_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_announcement_type_display()} - {self.route_title or self.route}"

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.QUEUED, self.Status.SENT} and (
            not self.repeat_until or self.repeat_until >= timezone.now()
        )


class DeliveryLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="delivery_logs")
    group = models.ForeignKey(TelegramGroup, on_delete=models.CASCADE, related_name="delivery_logs")
    is_repeated = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["announcement", "status"], name="taxi_delivery_ann_status_idx")]

    def __str__(self) -> str:
        return f"{self.announcement_id} -> {self.group_id}: {self.status}"


class Blacklist(models.Model):
    telegram_id = models.BigIntegerField(db_index=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return str(self.telegram_id)
