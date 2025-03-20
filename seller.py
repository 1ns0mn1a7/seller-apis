"""Модуль для автоматического обновления цен и остатков товаров на Ozon."""
import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получает список товаров магазина с Ozon через API.

    Args:
        last_id (str): Последний идентификатор для пагинации.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен API Ozon.

    Returns:
        dict: Словарь с данными о товарах из ответа API, содержащий ключи:
            "items" (list): Список товаров,
            "total" (int): Общее количество товаров,
            "last_id" (str): Последний идентификатор для пагинации.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> get_product_list("", "12345", "token123")
        {'items': [{'offer_id': 'ABC123', ...}], 'total': 1, 'last_id': 'xyz'}
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Извлекает артикулы всех товаров магазина Ozon.

    Выполняет запросы к API Ozon с использованием пагинации,
    собирает все товары и возвращает список их артикулов
    (offer_id).

    Args:
        client_id (str): Идентификатор клиента Ozon из переменных окружения.
        seller_token (str): Токен API Ozon из переменных окружения.

    Returns:
        list: Список строк с артикулами товаров.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> get_offer_ids("12345", "token123")
        ['ABC123', 'XYZ789']
        >>> get_offer_ids("", "")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """Обновляет цены товаров на Ozon через API.

    Отправляет список цен на сервер Ozon для обновления.

    Args:
        prices (list): Список словарей с данными о ценах,
            где каждый словарь содержит ключи:
            "offer_id",
            "price",
            "old_price",
            "currency_code",
            "auto_action_enabled".
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен API Ozon.

    Returns:
        dict: Ответ API в формате JSON.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> update_price([{"offer_id": "ABC123",
        ...                "price": "5990",
        ...                "old_price": "0",
        ...                "currency_code": "RUB",
        ...                "auto_action_enabled": "UNKNOWN"}],
        ...              "12345", "token123")
        {'result': [{'offer_id': 'ABC123', 'updated': True}, ...]}
        >>> update_price([], "12345", "token123")
        {'result': []}
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновляет остатки товаров на Ozon через API.

    Отправляет список остатков на сервер Ozon для обновления.

    Args:
        stocks (list): Список словарей с данными об остатках,
            где каждый словарь содержит ключи:
                "offer_id" (str): Артикул товара,
                "stock" (int): Количество на складе.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен API Ozon.

    Returns:
        dict: Ответ API в формате JSON.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> update_stocks([{"offer_id": "ABC123", "stock": 10}],
        ...               "12345", "token123")
        {'result': [{'offer_id': 'ABC123', 'updated': True}, ...]}
        >>> update_stocks([], "12345", "token123")
        {'result': []}
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачивает и обрабатывает файл остатков с сайта Casio.

    Загружает ZIP-архив с сайта, извлекает файл Excel,
    читает данные о часах и возвращает их в виде списка словарей.
    После обработки файл удаляется.

    Returns:
        list: Список словарей с данными об остатках часов
            (ключи: "Код", "Количество", "Цена" и др.).

    Raises:
        requests.exceptions.RequestException: Если загрузка с сайта не удалась.
        OSError: Если возникла ошибка при работе с файлами.

    Examples:
        >>> download_stock()
        [{'Код': 'ABC123', 'Количество': '5', 'Цена': "5'990.00 руб."}, ...]
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """Формирует список остатков для загрузки на Ozon.

    Сравнивает остатки с Casio с артикулами Ozon,
    приводит количество к числовому виду
    и добавляет нулевые остатки для отсутствующих товаров.

    Args:
        watch_remnants (list): Список словарей с данными об остатках с Casio,
            где каждый словарь содержит "Код" и "Количество".
        offer_ids (list): Список строк с артикулами товаров с Ozon.

    Returns:
        list: Список словарей с остатками в формате
            {"offer_id": str, "stock": int}.

    Examples:
        >>> create_stocks([{"Код": "ABC123", "Количество": "5"}],
        ...               ["ABC123", "XYZ789"])
        [{'offer_id': 'ABC123', 'stock': 5},
        {'offer_id': 'XYZ789', 'stock': 0}]
        >>> create_stocks([], ["ABC123"])
        [{'offer_id': 'ABC123', 'stock': 0}]
    """
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Формирует список цен для загрузки на Ozon.

    Создает данные о ценах на основе остатков с Casio,
    фильтруя по артикулам Ozon.

    Args:
        watch_remnants (list): Список словарей с данными об остатках с Casio,
            где каждый словарь содержит "Код" и "Цена".
        offer_ids (list): Список строк с артикулами товаров с Ozon.

    Returns:
        list: Список словарей с ценами в формате
            {"offer_id": str, "price": str, "old_price": str,
             "currency_code": str, "auto_action_enabled": str}.

    Examples:
        >>> create_prices([{"Код": "ABC123", "Цена": "5'990.00 руб."}],
        ...               ["ABC123"])
        [{'auto_action_enabled': 'UNKNOWN', 'currency_code': 'RUB',
          'offer_id': 'ABC123', 'old_price': '0', 'price': '5990'}]
        >>> create_prices([], ["ABC123"])
        []
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """Преобразует строковое представление цены в числовой формат для загрузки.

    Убирает все символы, кроме цифр, из строки с ценой
    и возвращает целую часть.

    Args:
        price (str): Строка с ценой, например, "5'990.00 руб." или "1234.50".

    Returns:
        str: Целая часть цены в виде строки, содержащей только цифры.

    Examples:
        >>> price_conversion("5'990.00 руб.")
        '5990'
        >>> price_conversion("1234.50")
        '1234'
        >>> price_conversion("")
        ''
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделяет список на части по заданному количеству элементов.

    Генерирует подсписки из исходного списка с шагом n.

    Args:
        lst (list): Список для разделения, например, список цен или остатков.
        n (int): Размер каждой части.

    Returns:
        generator: Итератор, возвращающий подсписки.

    Examples:
        >>> list(divide([1, 2, 3, 4], 2))
        [[1, 2], [3, 4]]
        >>> list(divide([], 2))
        []
    """
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Загружает цены на Ozon асинхронно.

    Получает артикулы, формирует цены и отправляет их частями по 1000 записей.

    Args:
        watch_remnants (list): Список словарей с данными об остатках с Casio.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен API Ozon.

    Returns:
        list: Список сформированных цен.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> await upload_prices([{"Код": "ABC123", "Цена": "5'990.00 руб."}],
        ...                     "12345", "token123")
        [{'offer_id': 'ABC123', 'price': '5990', ...}]
        >>> await upload_prices([], "12345", "token123")
        []
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Загружает остатки на Ozon асинхронно.

    Получает артикулы, формирует остатки, отправляет их частями по 100 записей
    и возвращает ненулевые остатки и полный список.

    Args:
        watch_remnants (list): Список словарей с данными об остатках с Casio.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен API Ozon.

    Returns:
        tuple: Кортеж из двух списков: ненулевые остатки и все остатки.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> await upload_stocks([{"Код": "ABC123", "Количество": "5"}],
        ...                     "12345", "token123")
        ([{'offer_id': 'ABC123', 'stock': 5}],
         [{'offer_id': 'ABC123', 'stock': 5}])
        >>> await upload_stocks([], "12345", "token123")
        ([], [])
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    """Основная функция для запуска обновления цен и остатков на Ozon.

    Загружает данные окружения, получает остатки с Casio и обновляет Ozon.

    Raises:
        requests.exceptions.ReadTimeout: Если превышено время ожидания запроса.
        requests.exceptions.ConnectionError: При ошибке соединения с API.
        Exception: При прочих ошибках выполнения.
    """
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
