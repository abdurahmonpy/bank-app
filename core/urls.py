from django.contrib import admin
from django.urls import path
from app.views import jsonrpc_view
from app.payment_views import initiate_payment, payment_webhook, payment_status

urlpatterns = [
    path("admin/", admin.site.urls),
    # JSON-RPC 2.0 Microservice
    path("rpc/", jsonrpc_view, name="jsonrpc_endpoint"),
    path("api/v1/rpc/", jsonrpc_view, name="jsonrpc_v1_endpoint"),
    # Task 6 Payment Integration Simulation
    path("payment/initiate/", initiate_payment, name="payment_initiate"),
    path("payment/webhook/", payment_webhook, name="payment_webhook"),
    path("payment/status/", payment_status, name="payment_status"),
]
