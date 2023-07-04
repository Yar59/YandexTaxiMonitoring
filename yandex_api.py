import httpx


def get_address_from_coords(apikey: str, coords: tuple[float, float]) -> str:
    text_coords = ','.join([str(coord) for coord in coords])
    payload = {
        "apikey": apikey,
        "format": "json",
        "geocode": text_coords,
    }

    response = httpx.get("https://geocode-maps.yandex.ru/1.x/", params=payload)
    response.raise_for_status()
    try:
        address_str = response.json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["metaDataProperty"][
            "GeocoderMetaData"]["AddressDetails"]["Country"]["AddressLine"]
        return address_str
    except IndexError:
        return text_coords


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
        'class': 'econom'
    }
    response = httpx.get(url, params=payload)
    response.raise_for_status()
    return response.json()
