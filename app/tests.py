import json
import io
import os
from decimal import Decimal
import openpyxl
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.cache import cache
from app.models import Card, CardStatus, Transfer, TransferState, Error
from app.tasks import send_periodic_telegram_report
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
    calculate_exchange,
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
        self.assertTrue(validate_luhn("49927398716"))
        self.assertFalse(validate_luhn("49927398717"))

    def test_prepare_message(self):
        msg = prepare_message("8600123456789012", Decimal("150000.00"), lang="UZ")
        self.assertIn("Sizning kartangiz", msg)
        self.assertIn("150,000.00 UZS", msg)

    def test_calculate_exchange(self):
        self.assertEqual(calculate_exchange(100, "840"), Decimal("1280000.00"))
        self.assertEqual(calculate_exchange(100, "643"), Decimal("13500.00"))
        self.assertEqual(calculate_exchange(50000, "860"), Decimal("50000.00"))


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

    def test_populate_command(self):
        call_command("PopulateCommand")
        self.assertTrue(Error.objects.filter(code=32700).exists())
        self.assertTrue(Error.objects.filter(code=32707).exists())


class AdminExcelImportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser("admin", "admin@example.com", "password123")
        self.client.login(username="admin", password="password123")

    def test_admin_import_excel(self):
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


class TransferRPCTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        call_command("PopulateCommand")

        self.sender = Card.objects.create(
            card_number="8600123412341234",
            expire="12/26",
            phone="+998901234567",
            status=CardStatus.ACTIVE,
            balance=Decimal("2000000.00"),
        )
        self.receiver = Card.objects.create(
            card_number="8600567812345678",
            expire="08/27",
            phone="+998907654321",
            status=CardStatus.ACTIVE,
            balance=Decimal("50000.00"),
        )

    def _rpc(self, method: str, params: dict, rpc_id: int = 1):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": rpc_id,
        }
        res = self.client.post(
            "/rpc/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        return res.json()

    def test_transfer_lifecycle(self):
        ext_id = "tr-test-001"
        # 1. Create transfer
        create_res = self._rpc(
            "transfer.create",
            {
                "ext_id": ext_id,
                "sender_card_number": "8600123412341234",
                "sender_card_expiry": "12/26",
                "receiver_card_number": "8600567812345678",
                "sending_amount": 100000,
                "currency": "860",
            },
        )
        self.assertIn("result", create_res)
        self.assertEqual(create_res["result"]["state"], "created")
        self.assertTrue(create_res["result"]["otp_sent"])

        transfer = Transfer.objects.get(ext_id=ext_id)
        otp = transfer.otp

        # 2. Check state
        state_res = self._rpc("transfer.state", {"ext_id": ext_id})
        self.assertEqual(state_res["result"]["state"], "created")

        # 3. Wrong OTP attempt
        wrong_res = self._rpc("transfer.confirm", {"ext_id": ext_id, "otp": "000000"})
        self.assertIn("error", wrong_res)
        self.assertEqual(wrong_res["error"]["code"], 32712)

        # 4. Correct OTP confirm
        confirm_res = self._rpc("transfer.confirm", {"ext_id": ext_id, "otp": otp})
        self.assertIn("result", confirm_res)
        self.assertEqual(confirm_res["result"]["state"], "confirmed")

        # Verify balances updated atomically
        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()
        self.assertEqual(self.sender.balance, Decimal("1900000.00"))
        self.assertEqual(self.receiver.balance, Decimal("150000.00"))

        # 5. History check
        hist_res = self._rpc("transfer.history", {"card_number": "8600123412341234"})
        self.assertIn("result", hist_res)
        self.assertEqual(len(hist_res["result"]), 1)
        self.assertEqual(hist_res["result"][0]["ext_id"], ext_id)

    def test_transfer_cancel(self):
        ext_id = "tr-cancel-002"
        self._rpc(
            "transfer.create",
            {
                "ext_id": ext_id,
                "sender_card_number": "8600123412341234",
                "sender_card_expiry": "12/26",
                "receiver_card_number": "8600567812345678",
                "sending_amount": 50000,
                "currency": "860",
            },
        )
        cancel_res = self._rpc("transfer.cancel", {"ext_id": ext_id})
        self.assertIn("result", cancel_res)
        self.assertEqual(cancel_res["result"]["state"], "cancelled")

    def test_card_info(self):
        info_res = self._rpc("card.info", {"card_number": "8600 1234 1234 1234", "expiry": "12/26"})
        self.assertIn("result", info_res)
        self.assertEqual(info_res["result"]["card_status"], "active")
        self.assertEqual(info_res["result"]["balance"], 2000000.0)


class DataManagementTestCase(TestCase):
    def setUp(self):
        cache.clear()
        call_command("PopulateCommand")
        self.card = Card.objects.create(
            card_number="8600777788889999",
            expire="10/28",
            phone="+998907778899",
            status=CardStatus.ACTIVE,
            balance=Decimal("300000.00"),
        )
        self.transfer = Transfer.objects.create(
            ext_id="tr-dm-001",
            sender_card_number="8600777788889999",
            receiver_card_number="8600111122223333",
            sender_card_expiry="10/28",
            sending_amount=Decimal("50000.00"),
            currency="860",
            receiving_amount=Decimal("50000.00"),
            state=TransferState.CONFIRMED,
        )

    def test_periodic_report_task(self):
        res = send_periodic_telegram_report()
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["cards"], 1)
        self.assertGreaterEqual(res["transfers"], 1)

    def test_send_report_command(self):
        out = io.StringIO()
        call_command("send_report", stdout=out)
        self.assertIn("Report sent successfully", out.getvalue())

    def test_error_message_caching(self):
        msg1 = Error.get_message(32701, "uz")
        self.assertEqual(msg1, "Ext id allaqachon mavjud")
        # Second call should fetch from cache
        msg2 = Error.get_message(32701, "uz")
        self.assertEqual(msg2, msg1)

    def test_card_info_caching(self):
        client = Client()
        payload = {
            "jsonrpc": "2.0",
            "method": "card.info",
            "params": {"card_number": "8600777788889999", "expiry": "10/28"},
            "id": 1,
        }
        res1 = client.post("/rpc/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res1.status_code, 200)

        # Check that cache key was created
        cache_key = "card_info:8600777788889999:10/28"
        cached_val = cache.get(cache_key)
        self.assertIsNotNone(cached_val)
        self.assertEqual(cached_val["card_status"], "active")

    def test_export_transfers_excel_command(self):
        out_file = "test_transfers.xlsx"
        call_command("export_transfers_excel", output=out_file)
        self.assertTrue(os.path.exists(out_file))
        wb = openpyxl.load_workbook(out_file)
        ws = wb.active
        self.assertEqual(ws.title, "Transfers")
        self.assertGreaterEqual(ws.max_row, 2)
        if os.path.exists(out_file):
            os.remove(out_file)

    def test_export_cards_excel_command(self):
        out_file = "test_cards.xlsx"
        call_command("export_cards_excel", output=out_file)
        self.assertTrue(os.path.exists(out_file))
        wb = openpyxl.load_workbook(out_file)
        ws = wb.active
        self.assertEqual(ws.title, "Cards")
        self.assertGreaterEqual(ws.max_row, 2)
        if os.path.exists(out_file):
            os.remove(out_file)
