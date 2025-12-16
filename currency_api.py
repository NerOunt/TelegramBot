import requests
import logging
from datetime import datetime
from config import EXCHANGE_API_URL

logger = logging.getLogger(__name__)

class CurrencyAPI:
    def __init__(self):
        self.cache = {'data': None, 'timestamp': None}
        self.cache_timeout = 300

    def get_rates(self):
        current_time = datetime.now().timestamp()
        if (self.cache['data'] and self.cache['timestamp'] and 
            current_time - self.cache['timestamp'] < self.cache_timeout):
            return self.cache['data']
        
        try:
            response = requests.get(EXCHANGE_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('result') != 'success':
                logger.error(f"API вернул ошибку: {data.get('error-type', 'unknown')}")
                if self.cache['data']:
                    logger.info("Использую устаревшие данные из кэша")
                    return self.cache['data']
                return None
            
            api_rates = data['rates']
            rates = {'RUB': 1.0}
            
            for currency, rub_to_currency in api_rates.items():
                if currency != 'RUB' and rub_to_currency > 0:
                    rates[currency] = 1.0 / rub_to_currency
            
            result = {
                'rates': rates,
                'timestamp': data.get('time_last_update_unix', current_time),
                'date': data.get('time_last_update_utc', ''),
            }
            
            self.cache['data'] = result
            self.cache['timestamp'] = current_time
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при запросе к API: {e}")
            if self.cache['data']:
                logger.info("Использую устаревшие данные из кэша (ошибка сети)")
                return self.cache['data']
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Ошибка парсинга ответа API: {e}")
            if self.cache['data']:
                logger.info("Использую устаревшие данные из кэша (ошибка парсинга)")
                return self.cache['data']
            return None

    def get_currency_rate(self, currency_code):
        data = self.get_rates()
        if not data:
            return None
        
        code = currency_code.upper()
        if code in data['rates']:
            return {
                'rate': data['rates'][code],
                'timestamp': data['timestamp'],
                'date': data['date']
            }
        return None

    def convert_currency(self, amount, from_currency, to_currency):
        data = self.get_rates()
        if not data:
            return None

        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr not in data['rates']:
            logger.error(f"Валюта {from_curr} отсутствует в данных")
            return None
        if to_curr not in data['rates']:
            logger.error(f"Валюта {to_curr} отсутствует в данных")
            return None

        try:
            rub_total = amount * data['rates'][from_curr]
            result = rub_total / data['rates'][to_curr]
            return round(result, 4)
        except Exception as e:
            logger.error(f"Ошибка в convert_currency: {e}")
            return None
        
    def get_multiple_currencies(self, currencies_list):
            """Получить курсы нескольких валют."""
            data = self.get_rates()
            if not data:
                return None
            
            result = {}
            for curr in currencies_list:
                code = curr.upper()
                if code in data['rates']:
                    result[code] = data['rates'][code]
            return result or None