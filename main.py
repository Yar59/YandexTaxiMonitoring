import asyncio
import logging
from datetime import datetime
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
    get_first_place = auto()
    get_second_place = auto()
    search_taxi = auto()


def get_address_from_coords(apikey, coords):
    payload = {
        "apikey": apikey,
        "format": "json",
        "lang": "ru_RU",
        "kind": "house",
        "geocode": coords
    }

    response = httpx.get(url="https://geocode-maps.yandex.ru/1.x/", params=payload)
    response.raise_for_status()
    json_data = response.json()
    address_str = json_data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["metaDataProperty"][
        "GeocoderMetaData"]["AddressDetails"]["Country"]["AddressLine"]
    return address_str



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
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        dedent("""
            Этот бот поможет тебе отслеживать цену на такси
            и, если ты готов подождать, сообщит, когда цена снизится.
        """),
        reply_markup=markup,
    )

    return States.handle_menu


async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    reply_keyboard = [
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        dedent("""
                Пришли мне свою геопозицию или адрес места, откуда поедем.
            """),
        reply_markup=markup,
    )

    return States.get_first_place


async def get_first_place(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    reply_keyboard = [
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

    if update.message.text:
        try:
            context.user_data['first_place_name'] = update.message.text
            context.user_data['first_place'] = fetch_coordinates(context.bot_data['GEOCODER_API_KEY'],
                                                                 update.message.text)
        except httpx.HTTPError:

            await update.message.reply_text(
                dedent("""
                    Не смог найти такой адрес, попробуй еще раз.
                    Пришли мне свою геопозицию или адрес места, откуда поедем.
                """),
                reply_markup=markup,
            )
            return States.get_first_place

    else:
        context.user_data['first_place'] = (update.message.location.longitude, update.message.location.latitude)
        try:
            context.user_data['first_place_name'] = get_address_from_coords(context.bot_data['GEOCODER_API_KEY'],
                                                                            context.user_data['first_place'])
        except httpx.HTTPError:
            context.user_data['first_place_name'] = context.user_data['first_place']

    await update.message.reply_text(
        dedent(f"""
            Отлично, будем искать машину от {context.user_data['first_place_name']} {context.user_data['first_place']}.
            Пришли мне геопозицию или адрес места, куда поедем.
        """),
        reply_markup=markup,
    )
    return States.get_second_place


async def get_second_place(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    reply_keyboard = [
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

    if update.message.text:
        try:
            context.user_data['second_place_name'] = update.message.text
            context.user_data['second_place'] = fetch_coordinates(context.bot_data['GEOCODER_API_KEY'],
                                                                 update.message.text)
        except httpx.HTTPError:

            await update.message.reply_text(
                dedent("""
                    Не смог найти такой адрес, попробуй еще раз.
                    Пришли мне свою геопозицию или адрес места, откуда поедем.
                """),
                reply_markup=markup,
            )
            return States.get_second_place

    else:
        context.user_data['second_place'] = (update.message.location.longitude, update.message.location.latitude)
        try:
            context.user_data['second_place_name'] = get_address_from_coords(context.bot_data['GEOCODER_API_KEY'],
                                                                            context.user_data['second_place'])
        except httpx.HTTPError:
            context.user_data['second_place_name'] = context.user_data['second_place']

    reply_keyboard = [
        ['Поиск', ],
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        dedent(f"""
            Отлично, будем искать машину от {context.user_data['first_place_name']} {context.user_data['first_place']}
            до {context.user_data['second_place_name']} {context.user_data['second_place']}
            
        """),
        reply_markup=markup,
    )
    return States.search_taxi


async def fetch_taxi_price(context: ContextTypes.DEFAULT_TYPE):
    taxi_data = get_taxi(
        context.bot_data['TAXI_CLIENT_ID'],
        context.bot_data['TAXI_API_KEY'],
        context.user_data['first_place'],
        context.user_data['second_place'],
    )
    await context.bot.send_message(
        text=dedent(f"""
                Поездка от {context.user_data['first_place_name']} {context.user_data['first_place']}
                до {context.user_data['second_place_name']} {context.user_data['second_place']}
                будет стоить {taxi_data['options'][0]['price_text']}
            """),
        chat_id=context.job.chat_id,
    )


async def search_taxi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    context.user_data['in_search'] = True
    context.user_data['search_start_time'] = datetime.now()

    taxi_data = get_taxi(
        context.bot_data['TAXI_CLIENT_ID'],
        context.bot_data['TAXI_API_KEY'],
        context.user_data['first_place'],
        context.user_data['second_place'],
    )
    reply_keyboard = [
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        dedent(f"""
                    Поездка от {context.user_data['first_place_name']} {context.user_data['first_place']}
                    до {context.user_data['second_place_name']} {context.user_data['second_place']}
                    будет стоить {taxi_data['options'][0]['price_text']}
                """),
        reply_markup=markup,
    )

    context.job_queue.run_repeating(
        fetch_taxi_price,
        interval=6,
        user_id=update.message.from_user.id,
        chat_id=update.effective_chat.id,
    )

    return States.search_taxi


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
        entry_points=[CommandHandler('start', start)],
        states={
            States.handle_menu: [
                MessageHandler(filters.Regex('^Выбрать маршрут'), get_info)
            ],
            States.get_first_place: [
                MessageHandler(filters.Regex('^Отмена'), start),
                MessageHandler(filters.TEXT, get_first_place),
                MessageHandler(filters.LOCATION, get_first_place),
            ],
            States.get_second_place: [
                MessageHandler(filters.Regex('^Отмена'), start),
                MessageHandler(filters.TEXT, get_second_place),
                MessageHandler(filters.LOCATION, get_second_place),
            ],
            States.search_taxi: [
                MessageHandler(filters.Regex('^Отмена'), start),
                MessageHandler(filters.Regex('^Поиск'), search_taxi),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^cancel'), cancel),
        ],
    )

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
