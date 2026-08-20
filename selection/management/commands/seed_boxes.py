"""Idempotently seed the box/product catalogue from the initial fixture.

Safe to run on every deploy: it loads the fixture only when the catalogue is
empty, so it never overwrites boxes/products edited in the admin.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from selection.models import Box, Product


class Command(BaseCommand):
    help = "Load the initial box/product catalogue if the database is empty."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load the fixture even if data already exists (may overwrite).",
        )

    def handle(self, *args, **options):
        has_data = Box.objects.exists() or Product.objects.exists()
        if has_data and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Catalogue already populated — skipping seed "
                    "(use --force to reload)."
                )
            )
            return
        call_command("loaddata", "initial_data")
        self.stdout.write(self.style.SUCCESS("Seeded box/product catalogue."))
