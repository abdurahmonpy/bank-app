import json
import uuid
import logging
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from app.models import Payment, PaymentStatus, PaymentProvider
from app.utils import normalize_phone

logger = logging.getLogger("payment.gateway")


@csrf_exempt
def initiate_payment(request):
    """
    Initiates payment request with provider (Stripe, Payme, Click).
    Endpoint: POST /payment/initiate/
    Body:
    {
        "amount": 150000,
        "service_name": "Premium Subscription",
        "provider": "stripe",
        "user_phone": "+998901234567"
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    amount = data.get("amount")
    if not amount or Decimal(str(amount)) <= Decimal("0"):
        return JsonResponse({"error": "Valid positive amount is required"}, status=400)

    service_name = data.get("service_name", "General Service")
    provider = data.get("provider", PaymentProvider.STRIPE).lower()
    user_phone = normalize_phone(data.get("user_phone", ""))

    ext_id = data.get("ext_id") or f"pay-{uuid.uuid4().hex[:12]}"

    # Provider checkout URL simulation
    checkout_urls = {
        PaymentProvider.STRIPE: f"https://checkout.stripe.com/pay/{ext_id}",
        PaymentProvider.PAYME: f"https://checkout.paycom.uz/{ext_id}",
        PaymentProvider.CLICK: f"https://my.click.uz/services/pay?service_id=123&ext_id={ext_id}",
    }
    checkout_url = checkout_urls.get(provider, f"https://payment.example.com/pay/{ext_id}")

    payment = Payment.objects.create(
        ext_id=ext_id,
        provider=provider,
        service_name=service_name,
        amount=Decimal(str(amount)),
        user_phone=user_phone,
        status=PaymentStatus.PENDING,
        provider_transaction_id=f"tx-{uuid.uuid4().hex[:8]}",
        raw_response={"checkout_url": checkout_url, "initiated": True},
    )

    logger.info(f"Payment initiated: ext_id={ext_id} provider={provider} amount={amount}")
    return JsonResponse({
        "success": True,
        "ext_id": payment.ext_id,
        "provider": payment.provider,
        "amount": float(payment.amount),
        "status": payment.status,
        "checkout_url": checkout_url,
    }, status=201)


@csrf_exempt
def payment_webhook(request):
    """
    Receives and processes provider callbacks/webhooks.
    Endpoint: POST /payment/webhook/
    Body:
    {
        "ext_id": "pay-xxx",
        "event": "payment.succeeded",
        "provider_transaction_id": "ch_xxx"
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid webhook JSON"}, status=400)

    ext_id = data.get("ext_id")
    event = data.get("event", "payment.succeeded")
    tx_id = data.get("provider_transaction_id")

    payment = Payment.objects.filter(ext_id=ext_id).first()
    if not payment:
        logger.warning(f"Webhook received for unknown payment ext_id={ext_id}")
        return JsonResponse({"error": "Payment not found"}, status=404)

    # State transition based on webhook event
    if event in ["payment.succeeded", "success", "perform"]:
        payment.status = PaymentStatus.SUCCESS
    elif event in ["payment.failed", "error"]:
        payment.status = PaymentStatus.FAILED
    elif event in ["payment.cancelled", "cancel"]:
        payment.status = PaymentStatus.CANCELLED

    if tx_id:
        payment.provider_transaction_id = tx_id
    payment.raw_response = data
    payment.save(update_fields=["status", "provider_transaction_id", "raw_response", "updated_at"])

    logger.info(f"Webhook processed: ext_id={ext_id} status={payment.status}")
    return JsonResponse({
        "success": True,
        "ext_id": payment.ext_id,
        "status": payment.status,
    }, status=200)


def payment_status(request):
    """
    Queries payment status by ext_id.
    Endpoint: GET /payment/status/?ext_id=pay-xxx
    """
    ext_id = request.GET.get("ext_id")
    if not ext_id:
        return JsonResponse({"error": "Query param 'ext_id' is required"}, status=400)

    payment = Payment.objects.filter(ext_id=ext_id).first()
    if not payment:
        return JsonResponse({"error": "Payment not found"}, status=404)

    return JsonResponse({
        "ext_id": payment.ext_id,
        "provider": payment.provider,
        "service_name": payment.service_name,
        "amount": float(payment.amount),
        "status": payment.status,
        "provider_transaction_id": payment.provider_transaction_id,
        "created_at": payment.created_at.isoformat(),
        "updated_at": payment.updated_at.isoformat(),
    }, status=200)
