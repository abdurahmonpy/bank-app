from django.db import models
from decimal import Decimal
from app.utils import format_card, card_mask, format_phone, phone_mask


class CardStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    EXPIRED = "expired", "Expired"


class Card(models.Model):
    card_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="16-digit normalized card number (e.g. 8600123456789012)",
    )
    expire = models.CharField(
        max_length=10,
        help_text="Expiry date in MM/YY format",
    )
    phone = models.CharField(
        max_length=25,
        blank=True,
        null=True,
        help_text="Cardholder phone number",
    )
    status = models.CharField(
        max_length=10,
        choices=CardStatus.choices,
        default=CardStatus.ACTIVE,
        db_index=True,
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Card balance in UZS (between 0 and 1,200,000,000)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cards"
        ordering = ["-created_at"]
        verbose_name = "Bank Card"
        verbose_name_plural = "Bank Cards"

    def __str__(self):
        return f"{self.masked_card} ({self.status}) - {self.balance:,.2f} UZS"

    @property
    def formatted_card(self):
        return format_card(self.card_number)

    @property
    def masked_card(self):
        return card_mask(self.card_number)

    @property
    def formatted_phone_display(self):
        return format_phone(self.phone) if self.phone else "-"

    @property
    def masked_phone(self):
        return phone_mask(self.phone) if self.phone else "-"
