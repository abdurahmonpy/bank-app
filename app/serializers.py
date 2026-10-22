import re
from decimal import Decimal
from rest_framework import serializers
from app.utils import normalize_card, normalize_phone, normalize_expiry


class CardNumberField(serializers.CharField):
    def to_internal_value(self, data):
        val = super().to_internal_value(data)
        normalized = normalize_card(val)
        if len(normalized) != 16:
            raise serializers.ValidationError("Card number must be exactly 16 digits.")
        return normalized


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        val = super().to_internal_value(data)
        if not val:
            return ""
        normalized = normalize_phone(val)
        if normalized and not re.match(r"^\+998\d{9}$", normalized):
            raise serializers.ValidationError("Phone number must be valid +998XXXXXXXXX format.")
        return normalized


class ExpiryField(serializers.CharField):
    def to_internal_value(self, data):
        val = super().to_internal_value(data)
        normalized = normalize_expiry(val)
        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", normalized):
            raise serializers.ValidationError("Expiry must be in MM/YY format.")
        return normalized


class TransferCreateSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=100, required=True)
    sender_card_number = CardNumberField(required=True)
    sender_card_expiry = ExpiryField(required=True)
    receiver_card_number = CardNumberField(required=True)
    sending_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("100.00"), max_value=Decimal("1000000000.00"), required=True)
    currency = serializers.ChoiceField(choices=["860", "643", "840"], default="860")


class TransferConfirmSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=100, required=True)
    otp = serializers.CharField(max_length=10, min_length=4, required=True)


class TransferCancelSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=100, required=True)


class TransferStateSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=100, required=True)


class TransferHistorySerializer(serializers.Serializer):
    card_number = serializers.CharField(required=False, allow_blank=True, default=None)
    start_date = serializers.DateField(required=False, default=None)
    end_date = serializers.DateField(required=False, default=None)
    status = serializers.ChoiceField(choices=["created", "confirmed", "cancelled"], required=False, default=None)


class CardInfoSerializer(serializers.Serializer):
    card_number = CardNumberField(required=True)
    expiry = ExpiryField(required=True)
