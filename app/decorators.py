import time
import functools
import logging
import contextvars
from app.utils import card_mask

logger = logging.getLogger("rpc.audit")

# Context variable to store current HTTP request for RPC calls
current_http_request = contextvars.ContextVar("current_http_request", default=None)


def get_client_ip(request) -> str:
    """Extracts client IP address from HTTP request."""
    if not request:
        return "127.0.0.1"
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def mask_sensitive_data(data: dict) -> dict:
    """Masks card numbers and OTPs in logs for production safety."""
    masked = {}
    for k, v in data.items():
        if "card" in k.lower() and isinstance(v, str):
            masked[k] = card_mask(v)
        elif "otp" in k.lower():
            masked[k] = "******"
        else:
            masked[k] = v
    return masked


def safe_result_repr(res) -> str:
    """Safely represent jsonrpcserver Result objects without triggering oslash string bugs."""
    try:
        if hasattr(res, "_error"):
            return f"Error({res._error})"
        if hasattr(res, "value"):
            return f"Success({res.value})"
        return repr(res)
    except Exception:
        return type(res).__name__


def log_rpc_method(func):
    """
    Decorator for JSON-RPC methods (create, confirm, cancel):
    Tracks:
    - Client IP address
    - Request arguments (with sensitive data masked)
    - Response result / error
    - Processing duration in milliseconds
    - Traceability via ext_id
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        req = current_http_request.get()
        client_ip = get_client_ip(req)

        # Merge args and kwargs for logging
        call_params = mask_sensitive_data(kwargs)
        ext_id = kwargs.get("ext_id", "N/A")

        method_name = func.__name__
        logger.info(
            f"--> [RPC REQ] [{method_name}] IP={client_ip} ext_id={ext_id} params={call_params}"
        )

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000
            res_str = safe_result_repr(result)
            logger.info(
                f"<-- [RPC RES] [{method_name}] IP={client_ip} ext_id={ext_id} "
                f"duration={duration_ms:.2f}ms result={res_str}"
            )
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"<-- [RPC ERR] [{method_name}] IP={client_ip} ext_id={ext_id} "
                f"duration={duration_ms:.2f}ms exception={exc}",
                exc_info=True,
            )
            raise exc

    return wrapper
