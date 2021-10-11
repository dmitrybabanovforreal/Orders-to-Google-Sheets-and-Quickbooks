import datetime
from typing import List, Dict
from logging import getLogger
import json, os, traceback

import requests

import config


def get_orders(logger: getLogger, application_path: str) -> List:
    # API reference https://shopify.dev/docs/admin-api/rest/reference/orders/order#index-2021-04
    orders = []
    try:
        variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))
        url = f'https://{config.shopify_store}.myshopify.com/admin/api/2021-04/orders.json'
        headers = {'X-Shopify-Access-Token': config.shopify_password}
        params = {
            'status': 'open',
            'limit': 250,
            'since_id': variables['shopify']['last order id'],
            'created_at_min': '2021-07-01T00:00:00-07:00'
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        orders = response.json()['orders']

        # Continue requesting next pages if there are any
        while response.headers.get('Link'):
            url = response.headers.get('Link')
            headers = {'X-Shopify-Access-Token': config.shopify_password}
            params = {
                'status': 'open',
                'limit': 250,
                'since_id': variables['shopify']['last order id'],
                'created_at_min': '2021-07-01T00:00:00-07:00'
            }
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()

            orders.append(response.json()['orders'])

        logger.info(f'Shopify returned {str(len(orders))} orders')

        # Find the last id in the list
        for order in orders:
            if int(order['id']) > variables['shopify']['last order id']:
                variables['shopify']['last order id'] = int(order['id'])
        json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))

    except:
        logger.error(f'Could n\'t get orders from Shopify:')
        logger.error(traceback.format_exc())

    return orders


def get_delivery_dt(order: Dict) -> datetime.datetime:
    return datetime.datetime.fromisoformat(order['created_at'])
