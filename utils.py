def get_multiple_currencies(self, currencies_list):
        data = self.get_rates()
        if not data:
            return None
        
        result = {}
        for curr in currencies_list:
            code = curr.upper()
            if code in data['rates']:
                result[code] = data['rates'][code]
        return result or None 
import re
from datetime import datetime
from config import CURRENCY_NAMES, CURRENCY_SHORTCUTS

def parse_convert_input(text):
    if not text.strip():
        return None

    clean_text = re.sub(r'\s+', ' ', text.strip())
    lower_text = clean_text.lower()
    if re.search(r'\s+(в|to|in)\s+', lower_text):
        parts = re.split(r'\s+(в|to|in)\s+', lower_text)
        if len(parts) < 3:
            return None
        sources = parts[0]
        target_str = parts[2].strip()
        target_code = find_currency_code(target_str)
        if not target_code:
            return None

        tokens = sources.split()
        items = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if re.match(r'^-?[\d\.,]+$', token.replace(',', '.')):
                if i + 1 >= len(tokens):
                    return None
                amount_str = token
                curr_str = tokens[i + 1]
                try:
                    amount = float(amount_str.replace(',', '.'))
                except ValueError:
                    return None
                curr_code = find_currency_code(curr_str)
                if not curr_code:
                    return None
                items.append((amount, curr_code))
                i += 2
            else:
                i += 1

        if not items:
            return None
        if len(items) == 1:
            amount, from_code = items[0]
            return {
                'type': 'simple',
                'amount': amount,
                'from_currency': from_code,
                'to_currency': target_code
            }
        else:
            return {
                'type': 'multi',
                'items': items,
                'to_currency': target_code
            }

    parts = clean_text.split()
    if len(parts) == 1:
        # Запрос курса
        code = find_currency_code(parts[0])
        if code:
            return {
                'type': 'rate_only',
                'currency': code
            }

    if len(parts) == 3:
        try:
            amount = float(parts[0].replace(',', '.'))
        except ValueError:
            return None
        from_code = find_currency_code(parts[1])
        to_code = find_currency_code(parts[2])
        if from_code and to_code:
            return {
                'type': 'simple',
                'amount': amount,
                'from_currency': from_code,
                'to_currency': to_code
            }

    if len(parts) >= 4 and len(parts) % 2 == 1:
        target_code = find_currency_code(parts[-1])
        if not target_code:
            return None
        items = []
        for i in range(0, len(parts) - 1, 2):
            try:
                amount = float(parts[i].replace(',', '.'))
            except (ValueError, IndexError):
                return None
            curr_code = find_currency_code(parts[i + 1])
            if not curr_code:
                return None
            items.append((amount, curr_code))
        if items:
            if len(items) == 1:
                return {
                    'type': 'simple',
                    'amount': items[0][0],
                    'from_currency': items[0][1],
                    'to_currency': target_code
                }
            return {
                'type': 'multi',
                'items': items,
                'to_currency': target_code
            }

    return None


def find_currency_code(user_input):
    if not user_input or not isinstance(user_input, str):
        return None

    clean = user_input.lower().strip()
    if len(clean) == 3 and clean.isalpha():
        code = clean.upper()
        if code in CURRENCY_NAMES:
            return code

    if clean in CURRENCY_SHORTCUTS:
        return CURRENCY_SHORTCUTS[clean]

    for code, name in CURRENCY_NAMES.items():
        if clean in name.lower():
            return code

    return None

def format_currency_message(currency_data, currency_code):
    code = code.upper()
    if code == "RUB":
        return "• Российский рубль (RUB)\n  1 RUB = 1 RUB"
    if not currency_data:
        return "Данные временно недоступны"
    currency_name = CURRENCY_NAMES.get(currency_code, currency_code)
    rate = currency_data['rate']
    timestamp = currency_data['timestamp']
    if isinstance(timestamp, str):
        time_str = timestamp
    else:
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    message = (
        f"💱 *{currency_name} ({currency_code})*\n"
        f"• Курс к RUB: *{rate:.4f}*\n"
        f"• Время обновления: {time_str}\n"
        f"\n📊 1 RUB = {1/rate:.4f} {currency_code}"
    )
    return message


def format_multiple_currencies(rates):
    if not rates:
        return "Нет данных о курсах валют"
    message = "📈 *Курсы валют к RUB:*\n\n"
    for currency, rate in rates.items():
        name = CURRENCY_NAMES.get(currency, currency)
        message += f"• {name} ({currency}): *{rate:.4f}*\n"
        message += f"  1 {currency} = {rate:.2f} RUB\n"
        message += f"  1 RUB = {1/rate:.4f} {currency}\n\n"
    return message
def _parse_amount_currency_pairs(text):
    """Парсит '30usd 40 eur 50byn' → [(30, 'USD'), ...]"""
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    tokens = text.split()
    items = []
    i = 0
    while i < len(tokens):
        token = tokens[i].replace(',', '.')
        if re.match(r'^-?\d+(\.\d+)?$', token):
            if i + 1 >= len(tokens):
                return None
            amount = float(token)
            currency_str = tokens[i + 1]
            currency_code = find_currency_code(currency_str)
            if not currency_code:
                return None
            items.append((amount, currency_code))
            i += 2
        else:
            i += 1
    return items if items else None