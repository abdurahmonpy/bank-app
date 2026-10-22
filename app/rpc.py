import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction, models
from django.core.cache import cache
from jsonrpcserver import method, Success, Error, Result

from app.models import Card, Transfer, TransferState, Error as ErrorModel
from app.decorators import log_rpc_method, current_http_request, get_client_ip
from app.serializers import (
    TransferCreateSerializer,
    TransferConfirmSerializer,
    TransferCancelSerializer,
    CardInfoSerializer,
)
from app.utils import (
    normalize_card,
    normalize_expiry,
    generate_otp,
    calculate_exchange,
    send_telegram_message,
    card_mask,
    phone_mask,
    format_card,
    format_phone,
    check_rate_limit,
)

logger = logging.getLogger(__name__)


def get_error(code: int, custom_msg: str = None, lang: str = "en") -> Result:
    """Helper to return localized Error object from Error model"""
    msg = custom_msg or ErrorModel.get_message(code, lang=lang)
    return Error(code, msg)


@method(name="transfer.create")
@log_rpc_method
def transfer_create(
    ext_id: str,
    sender_card_number: str,
    sender_card_expiry: str,
    receiver_card_number: str,
    sending_amount: float,
    currency: str = "860",
) -> Result:
    """
    Starts a transfer request, validates cards, amounts, balance, and sends OTP.
    Validated using DRF Serializer and logged with IP and execution duration.
    """
    # 5.2 Request Validation using Serializers
    serializer = TransferCreateSerializer(data={
        "ext_id": ext_id,
        "sender_card_number": sender_card_number,
        "sender_card_expiry": sender_card_expiry,
        "receiver_card_number": receiver_card_number,
        "sending_amount": sending_amount,
        "currency": currency,
    })
    if not serializer.is_valid():
        first_err = list(serializer.errors.values())[0][0]
        return get_error(32706, f"Validation error: {first_err}")

    validated = serializer.validated_data
    clean_ext_id = validated["ext_id"]
    sender_clean = validated["sender_card_number"]
    receiver_clean = validated["receiver_card_number"]
    sender_norm_expiry = validated["sender_card_expiry"]
    amount_dec = validated["sending_amount"]
    str_curr = validated["currency"]

    # 1. Unique ext_id check
    if Transfer.objects.filter(ext_id=clean_ext_id).exists():
        return get_error(32701, "Ext id already exists")

    # 2. Sender card validation
    sender_card = Card.objects.filter(card_number=sender_clean).first()
    if not sender_card:
        return get_error(32706, "Sender card not found")

    if sender_norm_expiry != sender_card.expire:
        return get_error(32704, "Card expiry is not valid")

    if sender_card.status != "active":
        return get_error(32705, "Card is not active")

    if not sender_card.phone:
        return get_error(32703, "SMS service is not bind")

    # Calculate receiving amount in UZS
    receiving_amount = calculate_exchange(amount_dec, str_curr)

    if sender_card.balance < receiving_amount:
        return get_error(32702, "Balance is not enough")

    # 3. Receiver card validation
    receiver_card = Card.objects.filter(card_number=receiver_clean).first()
    if not receiver_card:
        return get_error(32706, "Receiver card not found")

    # 4. OTP Generation and Sending
    otp = generate_otp(6)
    msg = f"Tasdiqlash kodi: {otp}. O'tkazma summasi: {amount_dec} (Valyuta: {str_curr})."
    send_telegram_message(phone=sender_card.phone, message=msg)

    # 5. Create transfer record
    transfer = Transfer.objects.create(
        ext_id=clean_ext_id,
        sender_card_number=sender_clean,
        receiver_card_number=receiver_clean,
        sender_card_expiry=sender_norm_expiry,
        sender_phone=sender_card.phone,
        receiver_phone=receiver_card.phone,
        sending_amount=amount_dec,
        currency=str_curr,
        receiving_amount=receiving_amount,
        state=TransferState.CREATED,
        otp=otp,
        try_count=0,
    )

    logger.info(f"Transfer {clean_ext_id} created successfully with OTP {otp}")
    return Success({
        "ext_id": transfer.ext_id,
        "state": transfer.state,
        "otp_sent": True,
    })


@method(name="transfer.confirm")
@log_rpc_method
def transfer_confirm(ext_id: str, otp: str) -> Result:
    """
    Confirms transfer using OTP. Deducts sender balance and credits receiver balance.
    Enforces Rate Limiting (max 5 requests/minute per IP) and Serializer validation.
    """
    req = current_http_request.get()
    client_ip = get_client_ip(req)

    # 5.7 Rate Limiting check
    if not check_rate_limit(f"{client_ip}:confirm", limit=5, period=60):
        return get_error(32711, "Rate limit exceeded (max 5 requests per minute). Try later.")

    # 5.2 Serializer validation
    serializer = TransferConfirmSerializer(data={"ext_id": ext_id, "otp": otp})
    if not serializer.is_valid():
        first_err = list(serializer.errors.values())[0][0]
        return get_error(32706, f"Validation error: {first_err}")

    transfer = Transfer.objects.filter(ext_id=ext_id).first()
    if not transfer:
        return get_error(32706, "Transfer not found")

    if transfer.state == TransferState.CONFIRMED:
        return Success({"ext_id": transfer.ext_id, "state": "confirmed"})

    if transfer.state == TransferState.CANCELLED:
        return get_error(32706, "Transfer was cancelled")

    if transfer.try_count >= 3:
        return get_error(32711, "Count of try is reached")

    # Compare OTP
    if str(transfer.otp).strip() != str(otp).strip():
        transfer.try_count += 1
        transfer.save(update_fields=["try_count", "updated_at"])
        left_count = max(0, 3 - transfer.try_count)
        if left_count == 0:
            return get_error(32711, "Count of try is reached")
        return get_error(32712, f"OTP is wrong, left try count is {left_count}")

    # Process transfer balance updates atomically
    with transaction.atomic():
        sender = Card.objects.select_for_update().filter(card_number=transfer.sender_card_number).first()
        receiver = Card.objects.select_for_update().filter(card_number=transfer.receiver_card_number).first()

        if not sender or sender.balance < transfer.receiving_amount:
            return get_error(32702, "Balance is not enough")

        sender.balance -= transfer.receiving_amount
        sender.save(update_fields=["balance", "updated_at"])

        if receiver:
            receiver.balance += transfer.receiving_amount
            receiver.save(update_fields=["balance", "updated_at"])

        transfer.state = TransferState.CONFIRMED
        transfer.confirmed_at = timezone.now()
        transfer.save(update_fields=["state", "confirmed_at", "updated_at"])

    # Invalidate cached card infos
    cache.delete(f"card_info:{transfer.sender_card_number}:{transfer.sender_card_expiry}")

    logger.info(f"Transfer {ext_id} confirmed successfully.")
    return Success({
        "ext_id": transfer.ext_id,
        "state": "confirmed",
    })


@method(name="transfer.cancel")
@log_rpc_method
def transfer_cancel(ext_id: str) -> Result:
    """
    Cancels an unconfirmed transfer.
    """
    serializer = TransferCancelSerializer(data={"ext_id": ext_id})
    if not serializer.is_valid():
        return get_error(32706, "Invalid parameters")

    transfer = Transfer.objects.filter(ext_id=ext_id).first()
    if not transfer:
        return get_error(32706, "Transfer not found")

    if transfer.state == TransferState.CREATED:
        transfer.state = TransferState.CANCELLED
        transfer.cancelled_at = timezone.now()
        transfer.save(update_fields=["state", "cancelled_at", "updated_at"])
        return Success({"state": "cancelled"})

    return Success({"state": transfer.state})


@method(name="transfer.state")
def transfer_state(ext_id: str) -> Result:
    """
    Returns current state of a transfer.
    """
    transfer = Transfer.objects.filter(ext_id=ext_id).first()
    if not transfer:
        return get_error(32706, "Transfer not found")

    return Success({
        "ext_id": transfer.ext_id,
        "state": transfer.state,
    })


@method(name="transfer.history")
def transfer_history(
    card_number: str = None,
    start_date: str = None,
    end_date: str = None,
    status: str = None,
) -> Result:
    """
    Returns transfer history filtered by card_number, date range, and status.
    """
    queryset = Transfer.objects.all().order_by("-created_at")

    if card_number:
        clean = normalize_card(card_number)
        queryset = queryset.filter(
            models.Q(sender_card_number=clean) | models.Q(receiver_card_number=clean)
        )

    if status:
        queryset = queryset.filter(state=status.lower().strip())

    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)

    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)

    history = [
        {
            "ext_id": t.ext_id,
            "sender_card_number": card_mask(t.sender_card_number),
            "receiver_card_number": card_mask(t.receiver_card_number),
            "sending_amount": float(t.sending_amount),
            "currency": t.currency,
            "receiving_amount": float(t.receiving_amount),
            "state": t.state,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in queryset[:100]
    ]

    return Success(history)


@method(name="card.info")
def card_info(card_number: str, expiry: str) -> Result:
    """
    Fetches card info (card_status, balance, phone, masked_card).
    Cached for 30 seconds to reduce DB load in high-traffic fintech environments.
    """
    serializer = CardInfoSerializer(data={"card_number": card_number, "expiry": expiry})
    if not serializer.is_valid():
        first_err = list(serializer.errors.values())[0][0]
        return get_error(32706, f"Validation error: {first_err}")

    clean_card = serializer.validated_data["card_number"]
    norm_exp = serializer.validated_data["expiry"]

    cache_key = f"card_info:{clean_card}:{norm_exp}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Success(cached_data)

    card = Card.objects.filter(card_number=clean_card).first()
    if not card:
        return get_error(32706, "Card not found")

    if norm_exp != card.expire:
        return get_error(32704, "Card expiry is not valid")

    card_data = {
        "card_number": card.masked_card,
        "expire": card.expire,
        "phone": card.masked_phone,
        "card_status": card.status,
        "balance": float(card.balance),
    }

    # Cache response for 30 seconds
    cache.set(cache_key, card_data, timeout=30)

    return Success(card_data)
