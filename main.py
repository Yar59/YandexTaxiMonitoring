import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum, auto
from textwrap import dedent

import httpx
from environs import Env
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,

)

from yandex_api import fetch_coordinates, get_address_from_coords, get_taxi

logger = logging.getLogger(__name__)


class States(Enum):
    start = auto()
    handle_menu = auto()
    get_first_place = auto()
    get_second_place = auto()
    search_taxi = auto()


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    remove_job_if_exists(str(update.effective_chat.id), context)
    context.user_data['start_price'] = 0

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
            if not context.user_data['first_place']:
                raise httpx.HTTPError('Ошибка поиска места')

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
            Пришли мне <b>геопозицию</b> или <b>адрес места</b>, куда поедем.
        """),
        reply_markup=markup,
        parse_mode='HTML',
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
            if not context.user_data['second_place']:
                raise httpx.HTTPError('Ошибка поиска места')
        except httpx.HTTPError:

            await update.message.reply_text(
                dedent("""
                    Не смог найти такой адрес, попробуй еще раз.
                    Пришли мне свою <b>геопозицию</b> или <b>адрес места</b>, откуда поедем.
                """),
                reply_markup=markup,
                parse_mode='HTML'
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
            Отлично, будем искать машину!
            
            От: ➡️ <b>{context.user_data['first_place_name']}</b> {context.user_data['first_place']} ⬅️
            
            До: ➡️ <b>{context.user_data['second_place_name']}</b> {context.user_data['second_place']} ⬅️
        """),
        reply_markup=markup,
        parse_mode='HTML'
    )
    return States.search_taxi


async def fetch_taxi_price(context: ContextTypes.DEFAULT_TYPE):
    additional_text = ''

    taxi_data = get_taxi(
        context.bot_data['TAXI_CLIENT_ID'],
        context.bot_data['TAXI_API_KEY'],
        context.user_data['first_place'],
        context.user_data['second_place'],
    )
    class_level = taxi_data['options'][0]['class_level']

    if not context.user_data['start_price']:
        context.user_data['start_price'] = taxi_data['options'][0]['price']
        context.user_data['best_price'] = taxi_data['options'][0]['price']
        context.user_data['last_message_price'] = taxi_data['options'][0]['price']

    if taxi_data['options'][0]['price'] <= context.user_data['last_message_price'] * 0.95:
        additional_text = '‼️Цена на такси снизилась‼️'

    if context.user_data['best_price'] > taxi_data['options'][0]['price']:
        context.user_data['best_price'] = taxi_data['options'][0]['price']

    order_url = f'https://3.redirect.appmetrica.yandex.com/route' \
                f'?start-lat={context.user_data["first_place"][1]}' \
                f'&start-lon={context.user_data["first_place"][0]}' \
                f'&end-lat={context.user_data["second_place"][1]}' \
                f'&end-lon={context.user_data["second_place"][0]}' \
                f'&level={class_level}' \
                f'&appmetrica_tracking_id=1178268795219780156'
    keyboard = [
        [InlineKeyboardButton('Заказать', url=order_url), ],
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard, )

    if context.user_data.get('last_message', datetime.now() - timedelta(minutes=4)) + timedelta(
            minutes=3) < datetime.now() \
            or additional_text:
        context.user_data['last_message_price'] = taxi_data['options'][0]['price']
        context.user_data['last_message'] = datetime.now()
        await context.bot.send_message(
            text=dedent(f"""
                {additional_text}
                
                Поездка 
                От: ➡️ <b>{context.user_data['first_place_name']}</b> {context.user_data['first_place']} ⬅️
                До: ➡️ <b>{context.user_data['second_place_name']}</b> {context.user_data['second_place']} ⬅️
                
                Сейчас поездка стоит: <b>{taxi_data['options'][0]['price_text']}</b>
                
                Минимальная цена за время поиска: <b>{context.user_data['best_price']}</b> руб.
                
                Минимальная цена по этому маршруту
                (<i>без учета повышающего коэффициента</i>): <b>{taxi_data['options'][0]['min_price']}</b> руб.
                
                Поездка займет: {taxi_data['time_text']}
                
                ⬇️ Для заказа нажмите кнопку ниже ⬇️
            """),
            chat_id=context.job.chat_id,
            reply_markup=markup,
            parse_mode='HTML',
            disable_notification=not bool(len(additional_text)),
        )


async def search_taxi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    context.user_data['search_start_time'] = datetime.now()

    reply_keyboard = [
        ['Отмена', ],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        dedent(f"""
            Начинаю поиск!
        """),
        reply_markup=markup,
    )

    context.job_queue.run_repeating(
        fetch_taxi_price,
        interval=31,
        first=1,
        user_id=update.message.from_user.id,
        chat_id=update.effective_chat.id,
        name=str(update.effective_chat.id),
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
