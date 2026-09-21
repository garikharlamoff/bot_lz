import csv
import logging
from datetime import datetime
from io import StringIO
import httpx
import requests
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==== 0. Обиходные патчи / Логирование системное ====
_original_async_init = httpx.AsyncClient.__init__
_original_sync_init = httpx.Client.__init__


def _patched_async_init(self, *args, **kwargs):
    kwargs["verify"] = False
    return _original_async_init(self, *args, **kwargs)


def _patched_sync_init(self, *args, **kwargs):
    kwargs["verify"] = False
    return _original_sync_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_init
httpx.Client.__init__ = _patched_sync_init

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)

# ==== КОНФИГУРАЦИЯ ====
TELEGRAM_TOKEN = "8710200833:AAHjr_6x86yRsh3pOKGZqS-PgVuP8OotRno"  # Вставьте сюда ваш токен
CITY = "Minsk"
LOG_FILE = "bot_log.csv"


def log_event(
    user_id: int,
    username: str,
    motion: str,
    api_name: str,
    api_answer: str,
):

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    nick = f"@{username}" if username else "@NONE"

    clean_api_answer = str(api_answer).replace("\n", " ")

    log_line = f"{user_id} | {nick} | {motion} | {api_name} | {date_str} | {time_str} | {clean_api_answer}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)


def get_weather() -> str:
    try:
        url = f"https://wttr.in/{CITY}?format=j1"
        r = requests.get(url, timeout=10).json()
        forecast = []
        for day in r["weather"][:3]: 
            date = day["date"]
            avgtemp = day["avgtempC"]
            desc = day["hourly"][4]["weatherDesc"][0]["value"]
            forecast.append(f"{date}: {avgtemp}°C, {desc}")
        return "\n".join(forecast)
    except Exception as e:
        return f"Ошибка получения погоды: {e}"


def get_stock_price() -> str:
    try:
        ticker = "MSFT.US"
        url = f"https://stooq.com/q/l/?s={ticker}&f=sd2t2ohlcv&h&e=csv"
        r = requests.get(url, timeout=10)
        r.encoding = "utf-8"
        data = list(csv.DictReader(StringIO(r.text)))
        if data and "Close" in data[0]:
            price = data[0]["Close"]
            return f"Цена акции {ticker}: {price} USD"
        return "Не удалось получить данные по акции."
    except Exception as e:
        return f"Ошибка получения акций: {e}"


def get_btc_price() -> str:
    """API 3: CoinGecko (Курс Bitcoin)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=10).json()
        price = r["bitcoin"]["usd"]
        return f"Bitcoin: {price} USD"
    except Exception as e:
        return f"Ошибка получения курса BTC: {e}"


# ==== ХЭНДЛЕРЫ ТЕЛЕГРАМ ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [["Погода", "Акции", "Валюта"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет, выберите действие из меню:", reply_markup=reply_markup
    )
    log_event(
        user_id=user.id,
        username=user.username,
        motion="Command /start",
        api_name="NONE",
        api_answer="NONE",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    text_lower = text.lower()

    if text_lower == "погода":
        answer = get_weather()
        await update.message.reply_text(answer)
        log_event(
            user_id=user.id,
            username=user.username,
            motion="Button Click",
            api_name="wttr.in",
            api_answer=answer,
        )

    elif text_lower == "акции":
        answer = get_stock_price()
        await update.message.reply_text(answer)
        log_event(
            user_id=user.id,
            username=user.username,
            motion="Button Click",
            api_name="Stooq",
            api_answer=answer,
        )

    elif text_lower == "валюта":
        answer = get_btc_price()
        await update.message.reply_text(answer)
        log_event(
            user_id=user.id,
            username=user.username,
            motion="Button Click",
            api_name="CoinGecko",
            api_answer=answer,
        )

    else:
        response_text = f"Вы написали «{text}», я не знаю такой команды"
        await update.message.reply_text(response_text)

        log_event(
            user_id=user.id,
            username=user.username,
            motion="Keyboard typing",
            api_name="NONE",
            api_answer="NONE",
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()