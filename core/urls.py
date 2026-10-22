from django.contrib import admin
from django.urls import path
from app.views import jsonrpc_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("rpc/", jsonrpc_view, name="jsonrpc_endpoint"),
    path("api/v1/rpc/", jsonrpc_view, name="jsonrpc_v1_endpoint"),
]
