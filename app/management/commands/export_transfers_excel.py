import openpyxl
from django.core.management.base import BaseCommand
from app.models import Transfer
from app.utils import card_mask


class Command(BaseCommand):
    help = "Export transfers table to Excel (.xlsx) file for Data Management analysis"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="transfers_export.xlsx",
            help="Output Excel file path (default: transfers_export.xlsx)",
        )
        parser.add_argument(
            "--state",
            type=str,
            help="Filter by transfer state: created, confirmed, cancelled",
        )

    def handle(self, *args, **options):
        output_path = options.get("output", "transfers_export.xlsx")
        state_filter = options.get("state")

        queryset = Transfer.objects.all().order_by("-created_at")
        if state_filter:
            queryset = queryset.filter(state=state_filter.lower().strip())

        total = queryset.count()
        self.stdout.write(f"Exporting {total} transfers to Excel '{output_path}'...")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Transfers"

        headers = [
            "ID",
            "Ext ID",
            "Sender Card (Masked)",
            "Receiver Card (Masked)",
            "Sender Card Expiry",
            "Sender Phone",
            "Receiver Phone",
            "Sending Amount",
            "Currency",
            "Receiving Amount (UZS)",
            "State",
            "Try Count",
            "Created At",
            "Confirmed At",
            "Cancelled At",
        ]
        ws.append(headers)

        for t in queryset:
            ws.append([
                t.id,
                t.ext_id,
                card_mask(t.sender_card_number),
                card_mask(t.receiver_card_number),
                t.sender_card_expiry,
                t.sender_phone or "",
                t.receiver_phone or "",
                float(t.sending_amount),
                t.currency,
                float(t.receiving_amount),
                t.state,
                t.try_count,
                t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
                t.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if t.confirmed_at else "",
                t.cancelled_at.strftime("%Y-%m-%d %H:%M:%S") if t.cancelled_at else "",
            ])

        wb.save(output_path)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully exported {total} transfers to '{output_path}'!")
        )
