import logging
from enum import Enum, auto
from textwrap import dedent

import httpx
from environs import Env
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters, ContextTypes

logger = logging.getLogger(__name__)


class States(Enum):
    start = auto()
    handle_menu = auto()


def fetch_coordinates(apikey: str, address: str) -> tuple[float, float] | None:
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = httpx.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()["response"]["GeoObjectCollection"]["featureMember"]

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant["GeoObject"]["Point"]["pos"].split(" ")
    return lon, lat


def get_taxi(client_id: str | int, api_key: str, start_coordinates: tuple[float, float],
             end_coordinates: tuple[float, float]) -> dict:
    url = 'https://taxi-routeinfo.taxi.yandex.net/taxi_info'
    payload = {
        'clid': client_id,
        'apikey': api_key,
        'rll': f'{start_coordinates[0]},{start_coordinates[1]}~{end_coordinates[0]},{end_coordinates[1]}',
        'class': 'econom, business'
    }
    response = httpx.get(url, params=payload)
    response.raise_for_status()
    return response.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    reply_keyboard = [
        ["Выбрать маршрут", ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        dedent("""
            Этот бот поможет тебе отслеживать цену на такси
            и, если ты готов подождать, сообщит, когда цена снизится.
        """),
        reply_markup=markup,
    )

    return States.handle_menu


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    await update.message.reply_text(
        "Надеюсь, был тебе полезен, пока!",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    env = Env()
    env.read_env()

    geocoder_api_key = env('GEOCODER_API_KEY')
    taxi_client_id = env('TAXI_CLIENT_ID')
    taxi_api_key = env('TAXI_API_KEY')
    tg_token = env('TG_TOKEN')

    application = Application.builder().token(tg_token).build()

    application.bot_data['GEOCODER_API_KEY'] = geocoder_api_key
    application.bot_data['TAXI_CLIENT_ID'] = taxi_client_id
    application.bot_data['TAXI_API_KEY'] = taxi_api_key

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), cancel)],
    )

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
