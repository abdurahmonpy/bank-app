import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from jsonrpcserver import dispatch

from app.decorators import current_http_request
# Import rpc module to register all @method handlers
import app.rpc  # noqa: F401

logger = logging.getLogger(__name__)


@csrf_exempt
def jsonrpc_view(request):
    """
    JSON-RPC 2.0 endpoint handling all RPC requests.
    Supports transfer.create, transfer.confirm, transfer.cancel,
    transfer.state, transfer.history, and card.info.
    """
    if request.method != "POST":
        return HttpResponse(
            json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": 32713, "message": "Method is not allowed (POST required)"},
                "id": None,
            }),
            status=405,
            content_type="application/json",
        )

    # Set context for logging decorator
    token = current_http_request.set(request)
    try:
        request_body = request.body.decode("utf-8")
        response_str = dispatch(request_body)
        return HttpResponse(response_str, content_type="application/json")
    except Exception as e:
        logger.error(f"Error processing JSON-RPC request: {e}", exc_info=True)
        return HttpResponse(
            json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": 32706, "message": f"Server error: {str(e)}"},
                "id": None,
            }),
            status=500,
            content_type="application/json",
        )
    finally:
        current_http_request.reset(token)
