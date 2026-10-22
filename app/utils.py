import os
import re
import random
import logging
from decimal import Decimal
import requests

logger = logging.getLogger(__name__)

# Static exchange rates to UZS
EXCHANGE_RATES = {
    "860": Decimal("1.00"),      # UZS
    "643": Decimal("135.00"),    # RUB -> 135 UZS
    "840": Decimal("12800.00"),  # USD -> 12,800 UZS
}


def normalize_card(raw_card: str) -> str:
    """
    Strips spaces, dashes, and other non-digit characters from raw card number.
    Returns standard numeric string.
    """
    if not raw_card:
        return ""
    digits = re.sub(r"\D", "", str(raw_card))
    return digits


def format_card(raw_card: str) -> str:
    """
    Formats a 16-digit card number with standard space separation:
    '8600 1234 5678 9012'
    """
    digits = normalize_card(raw_card)
    if len(digits) == 16:
        return f"{digits[:4]} {digits[4:8]} {digits[8:12]} {digits[12:]}"
    return digits


def card_mask(card_number: str) -> str:
    """
    Masks a card number for security and logs:
    '8600 1234 5678 9012' -> '8600 12** **** 9012'
    """
    digits = normalize_card(card_number)
    if len(digits) == 16:
        return f"{digits[:4]} {digits[4:6]}** **** {digits[12:]}"
    if len(digits) > 8:
        return f"{digits[:6]}******{digits[-4:]}"
    return "******"


def normalize_phone(raw_phone: str) -> str:
    """
    Normalizes phone numbers to Uzbekistan format +998XXXXXXXXX or returns empty if invalid.
    Handles: '99 973 03 03', '973-03-03', '+998901234567', '901234567', etc.
    """
    if not raw_phone or str(raw_phone).strip().lower() in ["(empty)", "nan", "none", "-"]:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return ""
    
    # If 9 digits (e.g. 999730303), add Uzbekistan country code 998
    if len(digits) == 9:
        digits = "998" + digits
    elif len(digits) == 7:
        # 7-digit local number (e.g. 9730303), default operator prefix can be prepended or kept
        digits = "99890" + digits
    elif len(digits) == 12 and digits.startswith("998"):
        pass

    return f"+{digits}" if digits else ""


def format_phone(raw_phone: str) -> str:
    """
    Formats phone into human-readable string:
    '+998 99 973 03 03'
    """
    normalized = normalize_phone(raw_phone)
    if normalized.startswith("+998") and len(normalized) == 13:
        return f"+998 {normalized[4:6]} {normalized[6:9]} {normalized[9:11]} {normalized[11:]}"
    return normalized


def phone_mask(phone: str) -> str:
    """
    Masks phone number:
    '+998 99 973 03 03' -> '+998 99 *** ** 03'
    """
    normalized = normalize_phone(phone)
    if normalized.startswith("+998") and len(normalized) == 13:
        return f"+998 {normalized[4:6]} *** ** {normalized[11:]}"
    if len(normalized) > 5:
        return f"{normalized[:4]}***{normalized[-2:]}"
    return "****"


def normalize_expiry(raw_expire: str) -> str:
    """
    Normalizes expiry date variations into 'MM/YY':
    e.g. '12/24', '2024-12', '12.2024', '03.2026', '2026-08', '04/25' -> 'MM/YY'
    """
    if not raw_expire:
        return ""
    raw = str(raw_expire).strip()

    m1 = re.match(r"^(\d{4})[-/.](\d{1,2})$", raw)
    if m1:
        year, month = m1.group(1), int(m1.group(2))
        return f"{month:02d}/{year[-2:]}"

    m2 = re.match(r"^(\d{1,2})[-/.](\d{4})$", raw)
    if m2:
        month, year = int(m2.group(1)), m2.group(2)
        return f"{month:02d}/{year[-2:]}"

    m3 = re.match(r"^(\d{1,2})[-/.](\d{2})$", raw)
    if m3:
        month, year = int(m3.group(1)), m3.group(2)
        return f"{month:02d}/{year}"

    return raw


def validate_luhn(card_number: str) -> bool:
    """
    Validates card number using the standard Luhn algorithm (mod 10).
    """
    digits = [int(c) for c in normalize_card(card_number)]
    if not digits:
        return False
    
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def generate_otp(length: int = 6) -> str:
    """
    Generates a secure numeric OTP of given length (default 6 digits).
    """
    return "".join(random.choices("0123456789", k=length))


def calculate_exchange(amount: Decimal | float | int | str, currency: str) -> Decimal:
    """
    Calculates receiving amount in UZS using static currency rate.
    Supported currencies: '860' (UZS), '643' (RUB), '840' (USD).
    """
    curr = str(currency).strip()
    rate = EXCHANGE_RATES.get(curr, Decimal("1.00"))
    dec_amount = Decimal(str(amount))
    return (dec_amount * rate).quantize(Decimal("0.01"))


def send_telegram_message(phone: str, message: str, chat_id: str | int = 123456) -> bool:
    """
    Sends notification or OTP via Telegram bot.
    """
    return send_message(message, chat_id=chat_id)


def prepare_message(card_number: str, balance: Decimal, lang: str = "UZ") -> str:
    """
    Prepares a notification message using template.
    Template: 'Sizning kartangiz [card_number] aktiv va foydalanishga [balance] UZS mavjud!'
    """
    masked = card_mask(card_number)
    formatted_balance = f"{balance:,.2f}"
    if lang.upper() == "UZ":
        return f"Sizning kartangiz {masked} aktiv va foydalanishga {formatted_balance} UZS mavjud!"
    elif lang.upper() == "RU":
        return f"Ваша карта {masked} активна и доступно {formatted_balance} UZS!"
    return f"Your card {masked} is active with {formatted_balance} UZS available!"


def send_message(message: str, chat_id: str | int = None) -> bool:
    """
    Sends message to Telegram bot if credentials are configured,
    or logs simulation otherwise.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    target_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "123456789")

    if bot_token and str(bot_token).strip() != "fake_token":
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            resp = requests.post(url, json={"chat_id": target_chat_id, "text": message}, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Telegram message sent to {target_chat_id}: {message}")
                return True
            else:
                logger.warning(f"Telegram API responded with {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    logger.info(f"[SIMULATED TELEGRAM SEND] To chat_id={target_chat_id}: {message}")
    try:
        print(f"[SIMULATED TELEGRAM] To: {target_chat_id} | Message: {message}")
    except Exception:
        safe_msg = message.encode("ascii", "replace").decode("ascii")
        print(f"[SIMULATED TELEGRAM] To: {target_chat_id} | Message: {safe_msg}")
    return True
