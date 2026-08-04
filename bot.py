import logging
import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from config import TOKEN, MAIN_CURRENCIES, CURRENCY_NAMES
from currency_api import CurrencyAPI
from utils import (
    parse_convert_input, find_currency_code,
    format_currency_message, format_multiple_currencies
)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


SELECTING_CURRENCY = 1
SELECTING_CURRENCIES = 2  
SELECTING_FROM_CURRENCY = 3
AWAITING_AMOUNT = 4
SELECTING_TO_CURRENCY = 5
CONFIRM_CONVERT = 6
CONV_FROM = 10
CONV_AMOUNT = 11
CONV_TO = 12

currency_api = CurrencyAPI()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "🤖 *Я бот для отслеживания курсов валют*\n\n"
        "📊 *Доступные команды:*\n"
        "• /start - Начальное сообщение\n"
        "• /courses - Курсы основных валют\n"
        "• /convert - Конвертер валют\n"
        "• /help - Помощь и инструкции\n\n"
        "💡 *Примеры использования:*\n"
        "`/courses USD` - курс доллара\n"
        "`/convert 100 USD RUB` - конвертация\n"
        "`30 USD и 40 EUR в RUB` - множественная конвертация\n\n"
        "🔍 *Подсказка:* Можно вводить частичные названия валют.\n"
        "Например: 'руб', 'дол', 'евр'"
    )
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()  
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Справочная информация*\n\n"
        "🔹 *Основные команды:*\n"
        "• `/courses` :\n 1.Курсы основных валют (USD, EUR, CNY, BYN, KZT)\n 2.Курсы выбранных валют\n"
        "• `/courses [код]` - курс конкретной валюты\n"
        "• `/convert [сумма] [из] [в]` - конвертация\n\n"
        "🔹 *Примеры запросов:*\n"
        "`/courses EUR`\n"
        "`/convert 150 USD RUB`\n"
        "`50 EUR и 100 USD в RUB`\n\n"
        "🔹 *Поддерживаемые валюты:*\n"
    )
    
    currencies_list = list(CURRENCY_NAMES.items())
    for i in range(0, len(currencies_list), 5):
        chunk = currencies_list[i:i+5]
        help_text += " | ".join([f"{code}" for code, _ in chunk]) + "\n"
    
    help_text += "\n🔹 *Быстрая конвертация:*\n"
    help_text += "Просто отправьте сообщение вида:\n"
    help_text += "`100 USD в RUB` или `30 EUR и 50 USD в RUB`"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')
async def show_currency_list(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    buttons = []
    currencies = list(CURRENCY_NAMES.keys())
    for i in range(0, len(currencies), 4):
        row = []
        for code in currencies[i:i+4]:
            name = CURRENCY_NAMES[code]
            label = f"{code} ({name})"
            cb_data = f"conv_{mode}_{code}"
            row.append(InlineKeyboardButton(label, callback_data=cb_data))
        buttons.append(row)

    text = "Выберите валюту *в*:" if mode == "to" else "Выберите валюту *из*:"
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
async def courses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        selected_codes = []
        for arg in args:
            code = find_currency_code(arg)
            if code:
                selected_codes.append(code)
            else:
                await update.message.reply_text(f"❌ Валюта '{arg}' не найдена.Попробуйте USD,EUR")
                return
        rates_data = currency_api.get_rates()
        if not rates_data:
            await update.message.reply_text("⚠️ Данные недоступны. Попробуйте позже.")
            return

        selected_rates = {
            code: rates_data['rates'][code]
            for code in selected_codes
            if code in rates_data['rates']
        }

        if not selected_rates:
            await update.message.reply_text("❌ Не удалось получить курсы для указанных валют.")
            return

        message = format_multiple_currencies(selected_rates)
        await update.message.reply_text(message, parse_mode='Markdown')
        return 

    keyboard = [
        [InlineKeyboardButton("📊 Основные валюты", callback_data="main_courses")],
        [InlineKeyboardButton("🔍 Выбрать валюты", callback_data="select_currencies")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите, какие курсы показать:", reply_markup=reply_markup)

async def handle_course_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_courses":
        rates_data = currency_api.get_rates()
        if not rates_data:
            await query.edit_message_text("⚠️ Данные недоступны.")
            return

        main_rates = {
            curr: rates_data['rates'][curr]
            for curr in MAIN_CURRENCIES
            if curr in rates_data['rates']
        }

        message = format_multiple_currencies(main_rates)
        back_keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_courses")]]
        reply_markup = InlineKeyboardMarkup(back_keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif data == "select_currencies":
        context.user_data['selected_currencies'] = set()
        await show_currency_selection(update, context)

    elif data == "get_selected_courses":
        selected = context.user_data.get('selected_currencies', set())
        if not selected:
            await query.answer("❌ Вы не выбрали ни одной валюты!", show_alert=True)
            return

        rates_data = currency_api.get_rates()
        if not rates_data:
            await query.edit_message_text("⚠️ Данные недоступны.")
            return

        selected_rates = {
            curr: rates_data['rates'][curr]
            for curr in selected
            if curr in rates_data['rates']
        }

        if not selected_rates:
            await query.edit_message_text("❌ Не удалось получить курсы.")
            return

        message = format_multiple_currencies(selected_rates)
        back_keyboard = [[InlineKeyboardButton("⬅️ Назад к выбору", callback_data="select_currencies")]]
        reply_markup = InlineKeyboardMarkup(back_keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif data == "back_to_courses":
        keyboard = [
            [InlineKeyboardButton("📊 Основные валюты", callback_data="main_courses")],
            [InlineKeyboardButton("🔍 Выбрать валюты", callback_data="select_currencies")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите, какие курсы показать:", reply_markup=reply_markup)

    elif data.startswith("toggle_"):
        currency = data[7:]
        selected = context.user_data.setdefault('selected_currencies', set())
        if currency in selected:
            selected.remove(currency)
        else:
            selected.add(currency)
        await show_currency_selection(update, context)



async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        if len(context.args) == 3:
            amount_str, from_curr_raw, to_curr_raw = context.args
            try:
                amount = float(amount_str.replace(',', '.'))
            except ValueError:
                await update.message.reply_text("❌ Укажите корректную сумму (число).")
                return

            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть положительной.")
                return

            from_curr = from_curr_raw.upper()
            to_curr = to_curr_raw.upper()
            if from_curr not in CURRENCY_NAMES:
                await update.message.reply_text(f"❌ Валюта '{from_curr}' не поддерживается.")
                return

            if to_curr not in CURRENCY_NAMES:
                await update.message.reply_text(f"❌ Валюта '{to_curr}' не поддерживается.")
                return
            if from_curr == to_curr:
                await update.message.reply_text(f"✅ Валюты совпадают: {amount:.2f} {from_curr}")
                return
            converted = currency_api.convert_currency(amount, from_curr, to_curr)
            if converted is None:
                await update.message.reply_text("⚠️ Ошибка конвертации. Попробуйте позже.")
                return

            from_name = CURRENCY_NAMES.get(from_curr, from_curr)
            to_name = CURRENCY_NAMES.get(to_curr, to_curr)

            response = (
                f"💱 *Результат:*\n"
                f"• {amount:.2f} {from_name} ({from_curr}) =\n"
                f"• *{converted:.2f} {to_name} ({to_curr})*\n\n"
                f"📊 Курс: 1 {from_curr} = {converted/amount:.4f} {to_curr}"
            )
            await update.message.reply_text(response, parse_mode='Markdown')
            return
        input_text = " ".join(context.args)
        result = parse_convert_input(input_text)

        if not result:
            await update.message.reply_text(
                "❌ Неверный формат.\nПример: `/convert 100 USD RUB`"
            )
            return

        if result['type'] == 'simple':
            amount = result['amount']
            from_curr = result['from_currency'].upper()
            to_curr = result['to_currency'].upper()
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                await update.message.reply_text("❌ Укажите корректную сумму (число).")
                return

            if from_curr not in CURRENCY_NAMES:
                await update.message.reply_text(f"❌ Валюта '{from_curr}' не поддерживается.")
                return
            if to_curr not in CURRENCY_NAMES:
                await update.message.reply_text(f"❌ Валюта '{to_curr}' не поддерживается.")
                return
            if from_curr == to_curr:
                await update.message.reply_text(f"✅ Валюты совпадают: {amount:.2f} {from_curr}")
                return

            converted = currency_api.convert_currency(amount, from_curr, to_curr)
            if converted is None:
                await update.message.reply_text("⚠️ Ошибка конвертации. Попробуйте позже.")
                return

            from_name = CURRENCY_NAMES.get(from_curr, from_curr)
            to_name = CURRENCY_NAMES.get(to_curr, to_curr)
            response = (
                f"💱 *Результат:*\n"
                f"• {amount:.2f} {from_name} ({from_curr}) =\n"
                f"• *{converted:.2f} {to_name} ({to_curr})*\n\n"
                f"📊 Курс: 1 {from_curr} = {converted/amount:.4f} {to_curr}"
            )
            await update.message.reply_text(response, parse_mode='Markdown')

        elif result['type'] == 'multi':
            items = result['items']
            to_curr = result['to_currency'].upper()

            if to_curr not in CURRENCY_NAMES:
                await update.message.reply_text(f"❌ Валюта '{to_curr}' не поддерживается.")
                return

            total = 0.0
            details = []
            for amount, from_curr in items:
                from_curr = from_curr.upper()

                try:
                    amount = float(amount)
                    if amount <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    await update.message.reply_text("❌ Укажите корректную сумму (число).")
                    return

                if from_curr not in CURRENCY_NAMES:
                    await update.message.reply_text(f"❌ Валюта '{from_curr}' не поддерживается.")
                    return

                converted = currency_api.convert_currency(amount, from_curr, to_curr)
                if converted is None:
                    await update.message.reply_text(f"⚠️ Ошибка для {from_curr}")
                    return

                total += converted
                from_name = CURRENCY_NAMES.get(from_curr, from_curr)
                details.append(f"• {amount:.2f} {from_name} = {converted:.2f} {to_curr}")

            to_name = CURRENCY_NAMES.get(to_curr, to_curr)
            response = (
                f"💱 *Множественная конвертация:*\n\n"
                f"{chr(10).join(details)}\n\n"
                f"📊 *Итого:* {total:.2f} {to_name} ({to_curr})"
            )
            await update.message.reply_text(response, parse_mode='Markdown')

        return

    for key in list(context.user_data.keys()):
        if key.startswith('conv_'):
            del context.user_data[key]

    await update.message.reply_text("💱 Выберите валюту, *из* которой конвертировать:", parse_mode='Markdown')
    await show_currency_list(update, context, mode="from")
    return CONV_FROM


def build_currency_buttons(selected_currencies):
    buttons = []
    row = []
    for code, name in CURRENCY_NAMES.items():
        prefix = "✅ " if code in selected_currencies else ""
        button = InlineKeyboardButton(f"{prefix}{code} ({name})", callback_data=f"toggle_{code}")
        row.append(button)
        if len(row) == 2:  # 2 кнопки в строке
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)    
    buttons.append([InlineKeyboardButton("📈 Получить курс", callback_data="get_selected_courses")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_courses")])
    
    return buttons

async def handle_select_to_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_currency_list(update, context, mode="to")
    return SELECTING_TO_CURRENCY

async def show_currency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get('selected_currencies', set())
    keyboard = build_currency_buttons(selected)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"Выберите валюты для отображения (выбрано: {len(selected)}):"
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_convert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"✅ Получен callback: {data}")

    if data == "conv_add_more":
        await query.edit_message_text("➕ Выберите ещё одну валюту *из* которой конвертировать:")
        await show_currency_list(update, context, mode="from")
        return CONV_FROM

    elif data == "conv_select_to":
        await query.edit_message_text("➡️ Выберите валюту, *в* которую конвертировать:")
        await show_currency_list(update, context, mode="to")
        return CONV_TO

    elif data.startswith("conv_from_"):
        currency = data[10:]  
        logger.info(f"🔧 Выбрана валюта 'из': {currency}")
        context.user_data.setdefault('conv_items', []).append({'from': currency, 'amount': None})
        await query.edit_message_text(f"Введите сумму в {currency}:")
        return CONV_AMOUNT

    elif data.startswith("conv_to_"):
        to_curr = data[8:]
        logger.info(f"🔧 Выбрана валюта 'в': {to_curr}")
        context.user_data['conv_to'] = to_curr
        items = context.user_data.get('conv_items', [])
        if not items:
            await query.edit_message_text("❌ Сначала выберите хотя бы одну валюту 'из'.")
            return CONV_FROM

        text = "✅ Выбрано:\n" + "\n".join(
            f"• {item['from']}: {item['amount'] or '?'}" for item in items
        )
        text += f"\n\nВалюта: {to_curr}\n\nНажмите 'Конвертировать'."
        keyboard = [[InlineKeyboardButton("✅ Конвертировать", callback_data="conv_do")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return CONV_TO

    elif data == "conv_do":
        items = context.user_data.get('conv_items', [])
        to_curr = context.user_data.get('conv_to')
        if not items or not to_curr:
            await query.edit_message_text("❌ Недостаточно данных.")
            return ConversationHandler.END

        to_curr = to_curr.upper()
        for item in items:
            item['from'] = item['from'].upper()

        if any(item['amount'] is None for item in items):
            await query.answer("❌ Введите все суммы!", show_alert=True)
            return CONV_TO

        total = 0.0
        details = []
        for item in items:
            converted = currency_api.convert_currency(item['amount'], item['from'], to_curr)
            if converted is None:
                await query.edit_message_text(f"⚠️ Ошибка конвертации {item['from']}.")
                return ConversationHandler.END
            total += converted
            details.append(f"• {item['amount']:.2f} {item['from']} = {converted:.2f} {to_curr}")

        response = (
            f"💱 *Множественная конвертация:*\n\n"
            f"{chr(10).join(details)}\n\n"
            f"📊 *Итого:* {total:.2f} {to_curr}"
        )
        await query.edit_message_text(response, parse_mode='Markdown')
        return ConversationHandler.END

    else:
        await query.answer("Неизвестное действие.", show_alert=True)
        return CONV_FROM
    
async def handle_convert_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введите положительное число:")
        return CONV_AMOUNT
    items = context.user_data.get('conv_items', [])
    for item in reversed(items):
        if item['amount'] is None:
            item['amount'] = amount
            break
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="conv_add_more")],
        [InlineKeyboardButton("➡️ Выбрать 'в'", callback_data="conv_select_to")]
    ]
    await update.message.reply_text(
        f"Сумма {amount} сохранена.\nЧто дальше?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONV_FROM


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().strip(' /') == 'start':
        await start(update, context)
        return
    
    if text.upper() in CURRENCY_NAMES:
        context.args = [text.upper()]
        await courses_command(update, context)
        return

    result = parse_convert_input(text)
    
    if not result:
        if len(text.split()) == 1:
            curr_code = find_currency_code(text)
            if curr_code:
                context.args = [curr_code]
                await courses_command(update, context)
                return

        await update.message.reply_text(
            "🔄 Примеры:\n"
            "• 100 usd rub\n"
            "• 50 евро в рубли\n"
            "• 30 usd и 20 eur в rub\n"
            "• usd` → курс доллара"
        )
        return

    if result['type'] == 'simple':
        context.args = [str(result['amount']), result['from_currency'], result['to_currency']]
        await convert_command(update, context)
    elif result['type'] == 'multi':
        context.args = None 
        fake_args = []
        for amount, curr in result['items']:
            fake_args.append(str(amount))
            fake_args.append(curr)
        fake_args.append("в")
        fake_args.append(result['to_currency'])
        context.args = fake_args
        await convert_command(update, context)

    elif result['type'] == 'multi':
        await update.message.reply_text(
            "ℹ️ Множественная конвертация временно недоступна.\n"
            "Попробуйте по одной валюте: `100 usd в rub`"
        )

    else:
        await update.message.reply_text("Не удалось распознать запрос.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    try:
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже или используйте /help"
        )
    except:
        pass

def main():
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  
    PORT = int(os.environ.get("PORT", "8443"))  
    SECRET_PATH = os.environ.get("SECRET_PATH", TOKEN)  

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("courses", courses_command))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("convert", convert_command)],
        states={
            CONV_FROM: [
                CallbackQueryHandler(
                    handle_convert_callback,
                    pattern=r"^(conv_from_.+|conv_add_more|conv_select_to)$"
                )
            ],
            CONV_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_convert_amount)
            ],
            CONV_TO: [
                CallbackQueryHandler(
                    handle_convert_callback,
                    pattern=r"^(conv_to_.+|conv_do)$"
                )
            ],
        },
        fallbacks=[CommandHandler("convert", convert_command)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(conv_handler)   
    application.add_handler(
        CallbackQueryHandler(
            handle_course_selection,
            pattern=r"^(main_courses|select_currencies|get_selected_courses|back_to_courses|toggle_.+)$"
        )
    )  
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)
    
    print("🤖 Запуск бота через вебхук...")
    print(f"   Webhook URL: {WEBHOOK_URL}/{SECRET_PATH}")
    print(f"   Port: {PORT}")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=SECRET_PATH,
        webhook_url=f"{WEBHOOK_URL}/{SECRET_PATH}"
    )
if __name__ == '__main__':
    main() 

    

