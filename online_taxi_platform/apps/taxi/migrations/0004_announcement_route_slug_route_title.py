from django.db import migrations, models


ROUTE_TITLES = {
    "bagdod_toshkent": "Bag'dod ➡️ Toshkent",
    "rishton_toshkent": "Rishton ➡️ Toshkent",
    "buvayda_toshkent": "Buvayda ➡️ Toshkent",
    "uchkoprik_toshkent": "Uchko‘prik ➡️ Toshkent",
    "qoqon_toshkent": "Qo'qon ➡️ Toshkent",
    "fargona_toshkent": "Farg'ona ➡️ Toshkent",
    "toshkent_bagdod": "Toshkent ➡️ Bag'dod",
    "toshkent_rishton": "Toshkent ➡️ Rishton",
    "toshkent_buvayda": "Toshkent ➡️ Buvayda",
    "toshkent_uchkoprik": "Toshkent ➡️ Uchko‘prik",
    "toshkent_qoqon": "Toshkent ➡️ Qo'qon",
    "toshkent_fargona": "Toshkent ➡️ Farg'ona",
}

REGION_TO_TASHKENT_SLUGS = [
    "bagdod_toshkent",
    "rishton_toshkent",
    "buvayda_toshkent",
    "uchkoprik_toshkent",
]

TASHKENT_TO_REGION_SLUGS = [
    "toshkent_bagdod",
    "toshkent_rishton",
    "toshkent_buvayda",
    "toshkent_uchkoprik",
]


def backfill_route_display(apps, schema_editor):
    Announcement = apps.get_model("taxi", "Announcement")
    for announcement in Announcement.objects.select_related("route").iterator():
        target_slugs = list(dict.fromkeys(announcement.target_route_slugs or []))
        if target_slugs == REGION_TO_TASHKENT_SLUGS:
            route_slug = "region_to_tashkent"
            route_title = "Bag'dod, Rishton, Buvayda, Uchko‘prik ➡️ Toshkent"
        elif target_slugs == TASHKENT_TO_REGION_SLUGS:
            route_slug = "tashkent_to_region"
            route_title = "Toshkent ➡️ Bag'dod, Rishton, Buvayda, Uchko‘prik"
        else:
            route_slug = announcement.route.slug
            route_title = ROUTE_TITLES.get(route_slug, announcement.route.name)

        announcement.route_slug = route_slug
        announcement.route_title = route_title
        announcement.save(update_fields=["route_slug", "route_title"])


class Migration(migrations.Migration):
    dependencies = [
        ("taxi", "0003_announcement_mode_target_route_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="route_slug",
            field=models.SlugField(blank=True, db_index=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="announcement",
            name="route_title",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_route_display, migrations.RunPython.noop),
    ]
