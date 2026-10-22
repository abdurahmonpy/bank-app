from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from decimal import Decimal
import openpyxl

from app.models import Card, CardStatus
from app.utils import (
    format_card,
    card_mask,
    format_phone,
    phone_mask,
    normalize_card,
    normalize_phone,
    normalize_expiry,
    validate_luhn,
)


class HasPhoneFilter(admin.SimpleListFilter):
    title = "Phone availability"
    parameter_name = "has_phone"

    def lookups(self, request, model_admin):
        return [
            ("yes", "With Phone"),
            ("no", "Without Phone"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(phone__isnull=True).exclude(phone="")
        if self.value() == "no":
            return queryset.filter(phone__isnull=True) | queryset.filter(phone="")
        return queryset


class BalanceRangeFilter(admin.SimpleListFilter):
    title = "Balance Range"
    parameter_name = "balance_range"

    def lookups(self, request, model_admin):
        return [
            ("zero", "Zero (0 UZS)"),
            ("low", "< 1,000 UZS"),
            ("medium", "1,000 - 1,000,000 UZS"),
            ("high", "> 1,000,000 UZS"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "zero":
            return queryset.filter(balance=0)
        if self.value() == "low":
            return queryset.filter(balance__lt=1000)
        if self.value() == "medium":
            return queryset.filter(balance__gte=1000, balance__lte=1000000)
        if self.value() == "high":
            return queryset.filter(balance__gt=1000000)
        return queryset


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    change_list_template = "admin/app/card/change_list.html"

    list_display = [
        "id",
        "formatted_card_display",
        "masked_card_display",
        "expire",
        "formatted_phone_display",
        "status_badge",
        "balance_display",
        "created_at",
    ]
    list_filter = ["status", "expire", HasPhoneFilter, BalanceRangeFilter]
    search_fields = ["card_number", "phone"]
    ordering = ["-id"]

    def formatted_card_display(self, obj):
        return obj.formatted_card
    formatted_card_display.short_description = "Card Number"

    def masked_card_display(self, obj):
        return obj.masked_card
    masked_card_display.short_description = "Masked Card"

    def formatted_phone_display(self, obj):
        return obj.formatted_phone_display
    formatted_phone_display.short_description = "Phone"

    def balance_display(self, obj):
        return f"{obj.balance:,.2f} UZS"
    balance_display.short_description = "Balance"

    def status_badge(self, obj):
        colors = {
            "active": "green",
            "inactive": "gray",
            "expired": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: white; background: {}; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="card_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            excel_file = request.FILES["excel_file"]
            if not excel_file.name.endswith((".xlsx", ".xls")):
                messages.error(request, "Faqat .xlsx yoki .xls formatidagi fayllarni yuklash mumkin!")
                return redirect("..")

            try:
                workbook = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = workbook.active
                
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    messages.error(request, "Excel fayli bo'sh!")
                    return redirect("..")

                # Map headers
                header_row = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]
                
                def find_col(possible_names):
                    for idx, name in enumerate(header_row):
                        for p in possible_names:
                            if p in name:
                                return idx
                    return None

                card_idx = find_col(["card_number", "card", "karta"])
                expire_idx = find_col(["expire", "expiry", "muddat"])
                phone_idx = find_col(["phone", "telefon", "tel"])
                status_idx = find_col(["status", "holat"])
                balance_idx = find_col(["balance", "balans", "summa"])

                if card_idx is None:
                    messages.error(request, "Excelda 'card_number' ustuni topilmadi!")
                    return redirect("..")

                success_count = 0
                error_count = 0
                error_details = []

                for row_num, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue  # Skip empty rows

                    raw_card = row[card_idx] if card_idx is not None and card_idx < len(row) else None
                    raw_expire = row[expire_idx] if expire_idx is not None and expire_idx < len(row) else None
                    raw_phone = row[phone_idx] if phone_idx is not None and phone_idx < len(row) else None
                    raw_status = row[status_idx] if status_idx is not None and status_idx < len(row) else "active"
                    raw_balance = row[balance_idx] if balance_idx is not None and balance_idx < len(row) else 0

                    # 1. Clean & normalize card number
                    card_num = normalize_card(raw_card)
                    if len(card_num) != 16:
                        error_count += 1
                        error_details.append(f"Qator {row_num}: Karta raqami noto'g'ri ('{raw_card}')")
                        continue

                    # 2. Clean & normalize expiry
                    expire_norm = normalize_expiry(raw_expire)
                    if not expire_norm:
                        expire_norm = "12/26"

                    # 3. Clean & normalize phone
                    phone_norm = normalize_phone(raw_phone)

                    # 4. Status validation
                    status_clean = str(raw_status).strip().lower() if raw_status else "active"
                    if status_clean not in ["active", "inactive", "expired"]:
                        status_clean = "active"

                    # 5. Balance parsing
                    try:
                        if isinstance(raw_balance, (int, float, Decimal)):
                            balance_val = Decimal(str(raw_balance))
                        else:
                            clean_bal_str = str(raw_balance).replace(",", "").replace(" ", "").replace("UZS", "").strip()
                            balance_val = Decimal(clean_bal_str) if clean_bal_str else Decimal("0.00")
                        
                        if balance_val < 0 or balance_val > Decimal("1200000000.00"):
                            error_count += 1
                            error_details.append(f"Qator {row_num}: Balans chegaradan tashqarida ('{raw_balance}')")
                            continue
                    except Exception:
                        error_count += 1
                        error_details.append(f"Qator {row_num}: Balans son emas ('{raw_balance}')")
                        continue

                    # Save / update Card
                    Card.objects.update_or_create(
                        card_number=card_num,
                        defaults={
                            "expire": expire_norm,
                            "phone": phone_norm,
                            "status": status_clean,
                            "balance": balance_val,
                        },
                    )
                    success_count += 1

                msg = f"Excel import yakunlandi: {success_count} ta karta muvaffaqiyatli saqlandi/yangilandi."
                if error_count > 0:
                    msg += f" Xatolar soni: {error_count} ta."
                    messages.warning(request, msg)
                    for err in error_details[:5]:
                        messages.error(request, err)
                else:
                    messages.success(request, msg)

                return redirect("..")

            except Exception as e:
                messages.error(request, f"Faylni o'qishda xatolik yuz berdi: {str(e)}")
                return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Kartalarni Excel fayldan import qilish",
            "opts": self.model._meta,
        }
        return render(request, "admin/app/card/import_excel.html", context)
