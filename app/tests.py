from decimal import Decimal
import io
import os
import openpyxl
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.management import call_command
from app.models import Card, CardStatus
from app.utils import (
    normalize_card,
    format_card,
    card_mask,
    normalize_phone,
    format_phone,
    phone_mask,
    normalize_expiry,
    validate_luhn,
    prepare_message,
    send_message,
)


class UtilsTestCase(TestCase):
    def test_card_helpers(self):
        raw = "8600 1234 5678 9012"
        normalized = normalize_card(raw)
        self.assertEqual(normalized, "8600123456789012")
        self.assertEqual(format_card(normalized), "8600 1234 5678 9012")
        self.assertEqual(card_mask(normalized), "8600 12** **** 9012")

    def test_phone_helpers(self):
        raw1 = "99 973 03 03"
        self.assertEqual(normalize_phone(raw1), "+998999730303")
        self.assertEqual(format_phone(raw1), "+998 99 973 03 03")
        self.assertEqual(phone_mask(raw1), "+998 99 *** ** 03")

        raw2 = "+998901234567"
        self.assertEqual(normalize_phone(raw2), "+998901234567")

    def test_expiry_normalization(self):
        self.assertEqual(normalize_expiry("2025-07"), "07/25")
        self.assertEqual(normalize_expiry("03.2026"), "03/26")
        self.assertEqual(normalize_expiry("04/25"), "04/25")
        self.assertEqual(normalize_expiry("12/2024"), "12/24")

    def test_luhn_algorithm(self):
        # Known valid card test
        self.assertTrue(validate_luhn("49927398716"))
        self.assertFalse(validate_luhn("49927398717"))

    def test_prepare_message(self):
        msg = prepare_message("8600123456789012", Decimal("150000.00"), lang="UZ")
        self.assertIn("Sizning kartangiz", msg)
        self.assertIn("150,000.00 UZS", msg)


class CardModelTestCase(TestCase):
    def setUp(self):
        self.card = Card.objects.create(
            card_number="8600123456789012",
            expire="12/26",
            phone="+998901234567",
            status=CardStatus.ACTIVE,
            balance=Decimal("500000.00"),
        )

    def test_card_properties(self):
        self.assertEqual(self.card.formatted_card, "8600 1234 5678 9012")
        self.assertEqual(self.card.masked_card, "8600 12** **** 9012")
        self.assertEqual(self.card.formatted_phone_display, "+998 90 123 45 67")
        self.assertIn("8600 12** **** 9012", str(self.card))


class ManagementCommandsTestCase(TestCase):
    def setUp(self):
        Card.objects.create(
            card_number="8600111122223333",
            expire="05/27",
            phone="+998901112233",
            status=CardStatus.ACTIVE,
            balance=Decimal("250000.00"),
        )
        Card.objects.create(
            card_number="8600444455556666",
            expire="01/24",
            phone="",
            status=CardStatus.EXPIRED,
            balance=Decimal("0.00"),
        )

    def test_export_cards_command(self):
        output_file = "test_cards_export.csv"
        call_command("export_cards", status="active", output=output_file)
        self.assertTrue(os.path.exists(output_file))
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("8600111122223333", content)
            self.assertNotIn("8600444455556666", content)
        if os.path.exists(output_file):
            os.remove(output_file)

    def test_send_card_messages_command(self):
        out = io.StringIO()
        call_command("send_card_messages", status="active", stdout=out)
        self.assertIn("Finished", out.getvalue())


class AdminExcelImportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser("admin", "admin@example.com", "password123")
        self.client.login(username="admin", password="password123")

    def test_admin_import_excel(self):
        # Create in-memory excel file
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["card_number", "expire", "phone", "status", "balance"])
        ws.append(["8600 9999 8888 7777", "2026-09", "99 973 03 03", "active", "1,500.00"])
        
        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)
        file_stream.name = "test_import.xlsx"

        response = self.client.post("/admin/app/card/import-excel/", {"excel_file": file_stream}, follow=True)
        self.assertEqual(response.status_code, 200)

        card = Card.objects.filter(card_number="8600999988887777").first()
        self.assertIsNotNone(card)
        self.assertEqual(card.expire, "09/26")
        self.assertEqual(card.phone, "+998999730303")
        self.assertEqual(card.balance, Decimal("1500.00"))
