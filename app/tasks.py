import logging
from celery import shared_task
from django.db.models import Count, Sum
from app.models import Card, Transfer
from app.utils import send_message

logger = logging.getLogger(__name__)


@shared_task
def send_periodic_telegram_report():
    """
    Periodic Celery task sending bank statistics to Telegram:
    - Total card count (active, inactive, expired)
    - Total transfer count (created, confirmed, cancelled)
    - Total confirmed transfer volume in UZS
    """
    total_cards = Card.objects.count()
    active_cards = Card.objects.filter(status="active").count()
    total_transfers = Transfer.objects.count()
    confirmed_transfers = Transfer.objects.filter(state="confirmed").count()
    confirmed_volume = (
        Transfer.objects.filter(state="confirmed").aggregate(total=Sum("receiving_amount"))["total"] or 0
    )

    report_text = (
        "📊 *Davriy Hisobot (Bank App Stats)*\n\n"
        f"💳 *Jami kartalar:* {total_cards} ta (Faol: {active_cards})\n"
        f"🔄 *Jami o'tkazmalar:* {total_transfers} ta (Muvaffaqiyatli: {confirmed_transfers})\n"
        f"💰 *Muvaffaqiyatli aylanma:* {confirmed_volume:,.2f} UZS\n\n"
        "⚡ Tizim barqaror ishlamoqda."
    )

    logger.info(f"Sending periodic Telegram report: cards={total_cards}, transfers={total_transfers}")
    success = send_message(report_text)
    return {"success": success, "cards": total_cards, "transfers": total_transfers}
