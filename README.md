# Мониторинг цен на такси

Скрипт бота, который отслеживает цены на такси и сообщяет об их изменении.

## Стек
- `python-telegram-bot` - бот в телеграм
- `httpx` - запросы к сервисам яндекса
- `Yandex Geocoder API` - для получения адресов
- `Yandex taxi API` - для мониторинга цен на такси

## Установка
[python 3.10+](https://www.python.org/) должен быть установлен

Для установки зависимостей выполните команду 
```commandline
python3 -m pip install -r requirements.txt
```

Создайте файл `.env` в папке со скриптом и заполните его следующим образом:
```
GEOCODER_API_KEY=Ключ геокодера Яндекс
TAXI_CLIENT_ID=ID клиента API Яндекс такси
TAXI_API_KEY=ключ API Яндекс такси
TG_TOKEN=токен Вашего Telegram-бота
```

Для запуска бота выполните команду
```commandline
python3 main.py
```