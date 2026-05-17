from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxi", "0002_passenger_gender_people_count_char"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="mode",
            field=models.CharField(
                choices=[("auto", "Avtomatik"), ("manual", "Qo'lda")],
                default="auto",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="target_route_slugs",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
