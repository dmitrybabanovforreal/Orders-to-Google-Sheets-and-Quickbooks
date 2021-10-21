from typing import List, Dict
from logging import getLogger
from dateutil import tz
import json, os, traceback, datetime, csv

import requests

import config


def get_orders(logger: getLogger, application_path: str) -> List:
    # API reference https://api.rekki.com/swagger/index.html#operations-orders-ListOrdersBySupplierV3
    orders = []
    try:
        variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))
        url = 'https://api.rekki.com/api/integration/v3/orders/list'
        headers = {
            'Authorization': 'Bearer ' + config.rekki_token,
            'X-REKKI-Authorization-Type': 'supplier_api_token',
        }
        params = {
            'since': variables['rekki']['last order time'],  # Comes as a string from the previous API call
            "skip_integrated": False
        }
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()
    
        # Remove orders that may duplicate from the last call and save the last order's timestamp
        order_ids = []
        for order in response.json()['orders']:
            current_order_date_time_obj = datetime.datetime.strptime(order['inserted_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            latest_order_date_time_obj = datetime.datetime.strptime(variables['rekki']['last order time'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if current_order_date_time_obj > latest_order_date_time_obj:
                variables['rekki']['last order time'] = order['inserted_at']
    
            if order['reference'] not in variables['rekki']['last orders']:
                orders.append(order)
                order_ids.append(order['reference'])
    
        variables['rekki']['last orders'] = order_ids
        json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))
    
        logger.info(f'Rekki returned {str(len(orders))} orders')
    except:
        logger.error(f'Could n\'t get orders from Rekki:')
        logger.error(traceback.format_exc())

    return orders


def match_product_codes(orders: List, application_path: str) -> List:
    # Load the dictionary to match Rekki product codes with the ones from Shopify
    data = list(csv.reader(open(os.path.join(application_path, 'shopify-rekki product codes matching.csv'))))
    product_codes = {}
    for row in data:
        product_codes[row[0]] = row[1]  # the first item is Rekki, the second one is Shopify

    # Replace the Rekki product code using the productCodes dict
    for order in orders:
        for item in order['items']:
            item['product_code'] = product_codes.get(item['product_code'], item['product_code'])

    return orders


def get_delivery_dt(order: Dict) -> datetime.datetime:
    return (datetime.datetime
            .strptime(order['delivery_on'], '%Y-%m-%d')
            .replace(tzinfo=tz.gettz('UTC'))
            .astimezone(tz.gettz('America/Toronto')))
