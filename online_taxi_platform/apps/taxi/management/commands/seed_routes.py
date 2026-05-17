from django.core.management.base import BaseCommand

from constants.routes import DEFAULT_DATABASE_ROUTES
from apps.taxi.models import Route


class Command(BaseCommand):
    help = "Seed default taxi routes"

    DEFAULT_ROUTES = DEFAULT_DATABASE_ROUTES

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
