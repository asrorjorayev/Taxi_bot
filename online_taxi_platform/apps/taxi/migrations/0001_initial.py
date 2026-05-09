import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Route",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("from_city", models.CharField(max_length=120)),
                ("to_city", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["from_city", "to_city"]},
        ),
        migrations.CreateModel(
            name="TelegramUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("telegram_id", models.BigIntegerField(unique=True)),
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("role", models.CharField(choices=[("driver", "Haydovchi"), ("passenger", "Yo'lovchi"), ("admin", "Admin")], default="passenger", max_length=20)),
                ("is_blocked", models.BooleanField(default=False)),
                ("is_vip", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Blacklist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("telegram_id", models.BigIntegerField(db_index=True)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TelegramGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chat_id", models.BigIntegerField(unique=True)),
                ("title", models.CharField(max_length=255)),
                ("username", models.CharField(blank=True, max_length=255, null=True)),
                ("chat_type", models.CharField(max_length=32)),
                ("is_forum", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("bot_is_admin", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_successful_delivery", models.DateTimeField(blank=True, null=True)),
                ("last_failed_delivery", models.DateTimeField(blank=True, null=True)),
                ("routes", models.ManyToManyField(blank=True, related_name="telegram_groups", to="taxi.route")),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="Announcement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("announcement_type", models.CharField(choices=[("driver", "Haydovchi"), ("passenger", "Yo'lovchi")], max_length=20)),
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=20)),
                ("car_model", models.CharField(blank=True, max_length=120, null=True)),
                ("car_number", models.CharField(blank=True, max_length=50, null=True)),
                ("car_photo_file_id", models.CharField(blank=True, max_length=255, null=True)),
                ("seats", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("people_count", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("baggage", models.CharField(blank=True, max_length=255, null=True)),
                ("departure_time", models.CharField(max_length=120)),
                ("price", models.CharField(blank=True, max_length=120, null=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("repeat_interval_minutes", models.PositiveSmallIntegerField(default=0)),
                ("is_repeating", models.BooleanField(default=False)),
                ("repeat_until", models.DateTimeField(blank=True, null=True)),
                ("next_send_at", models.DateTimeField(blank=True, null=True)),
                ("send_count", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("queued", "Queued"), ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("route", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="announcements", to="taxi.route")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="announcements", to="taxi.telegramuser")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "is_repeating", "next_send_at"], name="taxi_ann_status_repeat_idx"),
                    models.Index(fields=["user", "created_at"], name="taxi_ann_user_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DeliveryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_repeated", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("telegram_message_id", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("announcement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_logs", to="taxi.announcement")),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_logs", to="taxi.telegramgroup")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["announcement", "status"], name="taxi_delivery_ann_status_idx")],
            },
        ),
    ]
