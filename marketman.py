import datetime
from typing import List, Dict
from logging import getLogger
import json, os, traceback
from dateutil import tz

import requests

import config


def get_orders(logger: getLogger, application_path: str, local_time: datetime.datetime) -> List:
    # API reference https://api-doc.marketman.com/?version=latest#3ade36ea-af67-4dc0-842b-eca56311d1e0
    orders = []
    try:
        variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))
        
        # Get the token first
        url = "https://api.marketman.com/v3/buyers/auth/GetToken"
        payload = {
            "APIKey": f"{config.marketman_api_key}",
            "APIPassword": f"{config.marketman_api_password}"
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        access_token = response.json()['Token']

        # Get the orders since the last order time
        # todo Obtain the API credentials and try to look into vendors and buyers orders, save the vendors/buyers ID
        
        url = "https://api.marketman.com/v3/vendors/orders/GetOrdersByDeliveryDate"
        payload = {
            "DateTimeFromUTC": local_time.strftime('%Y/%m/%d 00:00:00'),
            "VendorGuid": config.marketman_vendor_guid
        }
        headers = {
            'AUTH_TOKEN': f'{access_token}'
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Remove orders that may duplicate from the last call
        orderIds = []
        for order in response.json()['Orders']:
            if order['OrderNumber'] not in variables['marketman']['last orders']:
                orders.append(order)
                orderIds.append(order['OrderNumber'])
        variables['marketman']['last orders'] = orderIds
        json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))

        logger.info(f'Marketman returned {str(len(orders))} orders')
    except:
        logger.error(f'Could n\'t get orders from Marketman:')
        logger.error(traceback.format_exc())

    return orders


def get_delivery_dt(order: Dict) -> datetime.datetime:
    return (datetime.datetime.strptime(order['DeliveryDateUTC'], '%Y-%m-%d')
            .replace(tzinfo=tz.gettz('UTC'))
            .astimezone(tz.gettz('America/Toronto')))
