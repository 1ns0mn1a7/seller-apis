"""Модуль для автоматического обновления цен и остатков товаров на Яндекс Маркете."""
import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """Получает список товаров с Яндекс Маркета для заданной кампании.

    Args:
        page (str): Токен страницы для пагинации.
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        access_token (str): Токен доступа для авторизации в API.

    Returns:
        dict: Результат запроса с данными о товарах и пагинацией, содержащий:
            "offerMappingEntries" (list): Список товаров,
            "paging" (dict): Информация о пагинации.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> get_product_list("", "12345", "valid_token")
        {'offerMappingEntries': [{'offer': {'shopSku': 'ABC123'}}],
         'paging': {'nextPageToken': 'abc'}}
        >>> get_product_list("", "12345", "invalid_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """Обновляет остатки товаров на Яндекс Маркете.

    Args:
        stocks (list): Список словарей с данными об остатках,
        где каждый словарь содержит:
            "sku" (str): Артикул товара,
            "warehouseId" (str): ID склада,
            "items" (list): Список с информацией о количестве.
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        access_token (str): Токен доступа для авторизации в API.

    Returns:
        dict: Ответ API с результатом обновления.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> update_stocks([{"sku": "ABC123",
        ...               "warehouseId": "WH1",
        ...               "items": [{"count": 10, "type": "FIT",
        ...                         "updatedAt": "2023-...Z"}]}],
        ...               "12345", "valid_token")
        {'status': 'OK', 'result': [...]}
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """Обновляет цены товаров на Яндекс Маркете.

    Args:
        prices (list): Список словарей с данными о ценах,
        где каждый словарь содержит:
            "id" (str): Артикул товара,
            "price" (dict): Словарь с ключами "value" (int)
                и "currencyId" (str).
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        access_token (str): Токен доступа для авторизации в API.

    Returns:
        dict: Ответ API с результатом обновления.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> update_price([{"id": "ABC123",
        ...              "price": {"value": 5990,
        ...              "currencyId": "RUR"}}],
        ...              "12345", "valid_token")
        {'status': 'OK', ...}
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """Получает артикулы товаров с Яндекс Маркета.

    Args:
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        market_token (str): Токен доступа для авторизации в API.

    Returns:
        list: Список строк с артикулами товаров (shopSku).

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> get_offer_ids("12345", "valid_token")
        ['ABC123', 'DEF456', ...]
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Формирует данные об остатках товаров для Яндекс Маркета.

    Преобразует данные об остатках из источника в формат API Яндекс Маркета,
    добавляя недостающие товары с нулевым остатком.

    Args:
        watch_remnants (list):
        Список словарей с данными об остатках из источника,
            где каждый словарь содержит:
                "Код" (str): Артикул товара,
                "Количество" (str): Количество товара.
        offer_ids (list): Список строк с артикулами товаров с Яндекс Маркета.
        warehouse_id (str): Идентификатор склада.

    Returns:
        list: Список словарей с данными об остатках в формате API.

    Examples:
        >>> create_stocks([{"Код": "ABC123", "Количество": "5"}],
        ...               ["ABC123"], "WH1")
        [{'sku': 'ABC123', 'warehouseId': 'WH1',
        'items': [{'count': 5, 'type': 'FIT', ...}]}]
    """
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Формирует данные о ценах товаров для Яндекс Маркета.

    Преобразует данные о ценах из источника в формат API Яндекс Маркета.

    Args:
        watch_remnants (list): Список словарей с данными о ценах из источника,
            где каждый словарь содержит:
                "Код" (str): Артикул товара,
                "Цена" (str): Цена товара.
        offer_ids (list): Список строк с артикулами товаров с Яндекс Маркета.

    Returns:
        list: Список словарей с данными о ценах в формате API Яндекс Маркета.

    Examples:
        >>> create_prices([{"Код": "ABC123", "Цена": "5990"}], ["ABC123"])
        [{'id': 'ABC123', 'price': {'value': 5990, 'currencyId': 'RUR'}}]
        >>> create_prices([], ["ABC123"])
        []
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                # "feed": {"id": 0},
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    # "discountBase": 0,
                    "currencyId": "RUR",
                    # "vat": 0,
                },
                # "marketSku": 0,
                # "shopSku": "string",
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """Асинхронно обновляет цены товаров на Яндекс Маркете.

    Получает артикулы, формирует цены и отправляет их частями по 500 записей.

    Args:
        watch_remnants (list): Список словарей с данными о товарах из источника.
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        market_token (str): Токен доступа для авторизации в API.

    Returns:
        list: Список сформированных данных о ценах.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> await upload_prices([{"Код": "ABC123", "Цена": "5'990.00 руб."}],
        ...                     "12345", "valid_token")
        [{'id': 'ABC123', 'price': {'value': 5990, 'currencyId': 'RUR'}}]
        >>> await upload_prices([], "12345", "valid_token")
        []
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """Асинхронно обновляет остатки товаров на Яндекс Маркете.

    Получает артикулы, формирует остатки, отправляет их частями по 2000 записей
    и возвращает ненулевые и все остатки.

    Args:
        watch_remnants (list): Список словарей с данными о товарах из источника.
        campaign_id (str): Идентификатор кампании на Яндекс Маркете.
        market_token (str): Токен доступа для авторизации в API.
        warehouse_id (str): Идентификатор склада.

    Returns:
        tuple: Кортеж из двух списков - ненулевые остатки и все остатки.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API завершился ошибкой.

    Examples:
        >>> await upload_stocks([{"Код": "ABC123", "Количество": "5"}],
        ...                     "12345", "valid_token", "WH1")
        ([{'sku': 'ABC123', 'warehouseId': 'WH1', 'items': [{'count': 5, ...}]}],
         [{'sku': 'ABC123', 'warehouseId': 'WH1', 'items': [{'count': 5, ...}]}])
        >>> await upload_stocks([], "12345", "valid_token", "WH1")
        ([], [])
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    """Основная функция для обновления цен и остатков на Яндекс Маркете.

    Выполняет обновление цен и остатков для кампаний FBS и DBS,
    используя данные из источника watch_remnants.

    Raises:
        requests.exceptions.ReadTimeout: Если превышено время ожидания запроса.
        requests.exceptions.ConnectionError: При ошибке соединения с API.
        Exception: При прочих ошибках выполнения.
    """
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
