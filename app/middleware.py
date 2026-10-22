import os
import json
import logging
from django.http import JsonResponse
from app.utils import verify_hash

logger = logging.getLogger(__name__)


class RequestSignatureMiddleware:
    """
    Middleware to verify request HMAC-SHA256 signature against request-sign header.
    Activated when API_SECRET_KEY is configured in environment or when request-sign header is sent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only verify RPC POST requests
        if request.path.startswith(("/rpc/", "/api/v1/rpc/")) and request.method == "POST":
            secret = os.getenv("API_SECRET_KEY")
            signature = (
                request.headers.get("request-sign")
                or request.META.get("HTTP_REQUEST_SIGN")
            )

            # If secret is set or client sent signature header, enforce verification
            if secret and signature:
                body_str = request.body.decode("utf-8")
                if not verify_hash(body_str, secret, signature):
                    logger.warning(f"Invalid request signature from IP={request.META.get('REMOTE_ADDR')}")
                    return JsonResponse(
                        {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": 32706,
                                "message": "Invalid request signature (request-sign mismatch)",
                            },
                            "id": None,
                        },
                        status=403,
                    )

        return self.get_response(request)
