import datetime
from typing import List, Dict, Union, Tuple, Any
from logging import getLogger
from decimal import Decimal
import json, os, traceback, base64

import requests

import config


def get_qb_headers(application_path: str) -> Dict[str, str]:
    # Authorization API reference:
    # https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/faq
    variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))

    # This function updates the access token if it expired and then returns it
    if datetime.datetime.utcnow() > datetime.datetime.fromisoformat(variables['quickbooks']['best before']):
        url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
        headers = {
            'Accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + str(base64.b64encode((config.qb_id + ':' + config.qb_secret).encode("utf-8")), "utf-8")
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': variables['quickbooks']['refresh token']
        }
        response = requests.post(url, headers=headers, data=data)
        variables['quickbooks']['access token'] = response.json()['access_token']
        variables['quickbooks']['refresh token'] = response.json()['refresh_token']
        # Add almost an hour to account for slow requests speed:
        variables['quickbooks']['best before'] = (datetime.datetime.utcnow() + datetime.timedelta(seconds=3300)).isoformat()

        json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))  # Save them immediately

    return {
        'Authorization': 'Bearer ' + variables['quickbooks']['access token']
    }


def get_qb_obj(
        table: str,
        search_value: str,
        id_key: str,
        name_key: str,
        application_path: str
) -> Union[Tuple[None, None], Tuple[str, str]]:
    sql_statement = f"select * from {table} Where DisplayName = '{search_value}'"
    url = 'https://quickbooks.api.intuit.com/v3/company/' + \
          config.qb_company_id + \
          '/query?query=' + \
          sql_statement + \
          '&minorversion=62'
    response = requests.get(url, headers=get_qb_headers(application_path=application_path))
    response.raise_for_status()
    if not response.json()['QueryResponse'][table]:
        return None, None
    obj_id = response.json()['QueryResponse'][table][0][id_key]
    obj_name = response.json()['QueryResponse'][table][0][name_key]
    return obj_id, obj_name


def prepare_qb_line_item(
        platform: str,
        item_name_in_order: str,
        price: Decimal,
        qty: Decimal,
        discount: Decimal,
        logger: getLogger,
        application_path: str
) -> Union[Dict, None]:
    item_id, item_name = get_qb_obj(
        table='Item',
        search_value=item_name_in_order,
        id_key='Id',
        name_key='Name',
        application_path=application_path
    )

    if not item_id:
        logger.info(f'Line item {item_name_in_order} from {platform} wasn\'t found in QuickBooks. '
                     f'Estimate was not created')
        return None

    return {
        "DetailType": "SalesItemLineDetail",
        "Amount": float(price * qty),
        "SalesItemLineDetail": {
            "DiscountAmt": discount,
            "ItemRef": {
                "name": item_name,
                "value": str(item_id)
            },
            "Qty": int(qty),
            "UnitPrice": float(price),
        }
    }


def create_qb_estimate(
        platform: str,
        customer_name_in_order: str,
        line_items: List,
        order_number: str,
        logger: getLogger,
        application_path: str
) -> Any:
    # Estimate API reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/estimate
    if None in line_items:
        return None

    customer_id, customer_name = get_qb_obj(
        table='Customer',
        search_value=customer_name_in_order,
        id_key='Id',
        name_key='DisplayName',
        application_path=application_path
    )
    if not customer_id:
        logger.info(f'Customer {customer_name_in_order} from {platform} wasn\'t found in QuickBooks. '
                     f'Estimate was not created')
        return None

    data = {
        "CustomerRef": {
            "name": customer_name,
            "value": str(customer_id)
        },
        "Line": line_items
    }
    url = f"https://quickbooks.api.intuit.com/v3/company/{config.qb_company_id}/estimate"
    response = requests.post(url, headers=get_qb_headers(application_path=application_path), json=data)
    try:
        response.raise_for_status()
    except:
        logger.error(f"Estimate for order {order_number} from {platform} wasn\'t creted in QuickBooks:")
        logger.error(traceback.format_exc())