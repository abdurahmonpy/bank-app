import time
from django.core.management.base import BaseCommand
from app.models import Card
from app.utils import prepare_message, send_message


class Command(BaseCommand):
    help = "Send fake notification message to filtered cards (simulate Telegram bot sending)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            type=str,
            default="active",
            help="Filter by card status (default: 'active')",
        )
        parser.add_argument(
            "--lang",
            type=str,
            default="UZ",
            help="Language for notification: UZ, RU, EN (default: UZ)",
        )
        parser.add_argument(
            "--chat-id",
            type=str,
            dest="chat_id",
            help="Custom Telegram chat ID (optional)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum messages to send (default: 50)",
        )

    def handle(self, *args, **options):
        status = options.get("status", "active")
        lang = options.get("lang", "UZ")
        chat_id = options.get("chat_id")
        limit = options.get("limit", 50)

        queryset = Card.objects.filter(status=status)[:limit]
        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.WARNING(f"No cards found with status='{status}'."))
            return

        self.stdout.write(f"Sending messages for {total} cards with status='{status}' (lang={lang})...")

        sent_count = 0
        for card in queryset:
            # Prepare message using template:
            # "Sizning kartangiz [card_number] aktiv va foydalanishga [balance] UZS mavjud!"
            msg = prepare_message(card.card_number, card.balance, lang=lang)
            success = send_message(msg, chat_id=chat_id)
            if success:
                sent_count += 1
                self.stdout.write(f"[SENT] Card: {card.masked_card} | Phone: {card.formatted_phone_display} | Balance: {card.balance:,.2f}")

        self.stdout.write(self.style.SUCCESS(f"Finished: {sent_count}/{total} messages processed successfully."))
