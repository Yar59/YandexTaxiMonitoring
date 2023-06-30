import httpx
from environs import Env


def fetch_coordinates(apikey, address):
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


def get_taxi(client_id, api_key, start_coordinates, end_coordinates):
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


def main():
    env = Env()
    env.read_env()

    geocoder_api_key = env("GEOCODER_API_KEY")
    taxi_client_id = env('TAXI_CLIENT_ID')
    taxi_api_key = env('TAXI_API_KEY')


if __name__ == '__main__':
    main()
