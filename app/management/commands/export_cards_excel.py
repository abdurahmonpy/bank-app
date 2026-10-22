import openpyxl
from django.core.management.base import BaseCommand
from app.models import Card


class Command(BaseCommand):
    help = "Export cards table to Excel (.xlsx) file for Data Management analysis"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="cards_export.xlsx",
            help="Output Excel file path (default: cards_export.xlsx)",
        )
        parser.add_argument(
            "--status",
            type=str,
            help="Filter by status: active, inactive, expired",
        )

    def handle(self, *args, **options):
        output_path = options.get("output", "cards_export.xlsx")
        status_filter = options.get("status")

        queryset = Card.objects.all().order_by("-id")
        if status_filter:
            queryset = queryset.filter(status=status_filter.lower().strip())

        total = queryset.count()
        self.stdout.write(f"Exporting {total} cards to Excel '{output_path}'...")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cards"

        headers = [
            "ID",
            "Card Number (Normalized)",
            "Formatted Card",
            "Masked Card",
            "Expiry",
            "Phone",
            "Formatted Phone",
            "Status",
            "Balance (UZS)",
            "Created At",
        ]
        ws.append(headers)

        for c in queryset:
            ws.append([
                c.id,
                c.card_number,
                c.formatted_card,
                c.masked_card,
                c.expire,
                c.phone or "",
                c.formatted_phone_display,
                c.status,
                float(c.balance),
                c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            ])

        wb.save(output_path)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully exported {total} cards to '{output_path}'!")
        )
