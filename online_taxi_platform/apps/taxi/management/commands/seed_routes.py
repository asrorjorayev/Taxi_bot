from django.core.management.base import BaseCommand

from apps.taxi.models import Route


class Command(BaseCommand):
    help = "Seed default taxi routes"

    DEFAULT_ROUTES = [
        ("Bag'dod -> Toshkent", "bagdod_toshkent", "Bag'dod", "Toshkent"),
        ("Rishton -> Toshkent", "rishton_toshkent", "Rishton", "Toshkent"),
        ("Buvayda -> Toshkent", "buvayda_toshkent", "Buvayda", "Toshkent"),
        ("Qo'qon -> Toshkent", "qoqon_toshkent", "Qo'qon", "Toshkent"),
        ("Farg'ona -> Toshkent", "fargona_toshkent", "Farg'ona", "Toshkent"),
        ("Toshkent -> Bag'dod", "toshkent_bagdod", "Toshkent", "Bag'dod"),
        ("Toshkent -> Rishton", "toshkent_rishton", "Toshkent", "Rishton"),
        ("Toshkent -> Buvayda", "toshkent_buvayda", "Toshkent", "Buvayda"),
        ("Toshkent -> Qo'qon", "toshkent_qoqon", "Toshkent", "Qo'qon"),
        ("Toshkent -> Farg'ona", "toshkent_fargona", "Toshkent", "Farg'ona"),
    ]

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for name, slug, from_city, to_city in self.DEFAULT_ROUTES:
            _, was_created = Route.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "from_city": from_city,
                    "to_city": to_city,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Routes seeded. Created: {created}, updated: {updated}"))
