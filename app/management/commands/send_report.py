from django.core.management.base import BaseCommand
from app.tasks import send_periodic_telegram_report


class Command(BaseCommand):
    help = "Send periodic stats report (cards and transfers) to Telegram"

    def handle(self, *args, **options):
        self.stdout.write("Generating and sending Telegram stats report...")
        result = send_periodic_telegram_report()
        self.stdout.write(
            self.style.SUCCESS(
                f"Report sent successfully! Stats: {result['cards']} cards, {result['transfers']} transfers."
            )
        )
