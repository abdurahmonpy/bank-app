import csv
import sys
from decimal import Decimal
from django.core.management.base import BaseCommand
from app.models import Card
from app.utils import normalize_card, normalize_phone


class Command(BaseCommand):
    help = "Export cards to CSV file with optional filters (status, card_number, phone)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            type=str,
            help="Filter by card status: active, inactive, expired",
        )
        parser.add_argument(
            "--card-number",
            type=str,
            dest="card_number",
            help="Filter by card number (partial or exact)",
        )
        parser.add_argument(
            "--phone",
            type=str,
            help="Filter by phone number",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="cards_export.csv",
            help="Output CSV file path (default: cards_export.csv)",
        )

    def handle(self, *args, **options):
        queryset = Card.objects.all().order_by("-id")

        status = options.get("status")
        if status:
            queryset = queryset.filter(status=status.lower().strip())

        card_number = options.get("card_number")
        if card_number:
            clean_card = normalize_card(card_number)
            queryset = queryset.filter(card_number__icontains=clean_card)

        phone = options.get("phone")
        if phone:
            clean_phone = normalize_phone(phone)
            queryset = queryset.filter(phone__icontains=clean_phone or phone)

        output_path = options.get("output")

        total = queryset.count()
        self.stdout.write(f"Exporting {total} cards to '{output_path}'...")

        try:
            with open(output_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id",
                    "card_number",
                    "formatted_card",
                    "masked_card",
                    "expire",
                    "phone",
                    "formatted_phone",
                    "status",
                    "balance_uzs",
                    "created_at",
                ])

                for card in queryset:
                    writer.writerow([
                        card.id,
                        card.card_number,
                        card.formatted_card,
                        card.masked_card,
                        card.expire,
                        card.phone or "",
                        card.formatted_phone_display,
                        card.status,
                        f"{card.balance:.2f}",
                        card.created_at.strftime("%Y-%m-%d %H:%M:%S") if card.created_at else "",
                    ])

            self.stdout.write(self.style.SUCCESS(f"Successfully exported {total} cards to '{output_path}'!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Export error: {e}"))
