from typing import Dict
from decimal import Decimal
from dateutil import tz
import os, datetime, csv

import logging_module, shopify, rekki, marketman, notch, quickbooks, google_sheets


def get_table(file_name: str) -> Dict:
    data = list(csv.reader(open(os.path.join(application_path, file_name))))
    table = {}
    for row in data:
        table[row[0]] = row[1]
    return table


application_path = os.path.abspath(os.path.dirname(__file__))
localTime = datetime.datetime.utcnow().replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz('America/Toronto'))
logger = logging_module.get_logger(application_path=application_path, local_time=localTime)

# Obtain the orders data
orders = {
    'shopify': shopify.get_orders(logger=logger, application_path=application_path),
    'rekki': rekki.get_orders(logger=logger, application_path=application_path),
    'marketman': marketman.get_orders(logger=logger, application_path=application_path, local_time=localTime),
    'notch': notch.get_orders(logger=logger, application_path=application_path)
}

# Load the dictionary with the location info per each product
# The first item is product code, the second one is location
productLocation = get_table('product codes location.csv')

# Load the dictionary with the customer rank info
# The first item is customer ID, the second one is rank int()
customerRank = get_table('customer rank.csv')

# Match the Rekki product codes with Shopify codes
orders['rekki'] = rekki.match_product_codes(orders=orders['rekki'], application_path=application_path)

# todo Add the location information using the productLocation dictionary

# Get the existing data from Google Sheets
ssData = google_sheets.get_sheet_data()

# Add the orders with delivery date starting from today to the spreadsheet
for order in orders['shopify']:
    deliveryDateTime = shopify.get_delivery_dt(order)
    customerName = (order['customer']['first_name'] + ' ' + order['customer']['last_name']).strip()
    for item in order['line_items']:
        ssData = google_sheets.add_order_to_sheet_data(
            ss_data=ssData,
            delivery_dt=deliveryDateTime,
            local_dt=localTime,
            platform='Shopify',
            order_id=order['id'],
            customer_name=customerName,
            quantity=item['quantity'],
            item_name=item['name'],
            notes='',
            customer_rank=customerRank.get(customerName, '')
        )

for order in orders['rekki']:
    deliveryDateTime = rekki.get_delivery_dt(order)
    for item in order['items']:
        ssData = google_sheets.add_order_to_sheet_data(
            ss_data=ssData,
            delivery_dt=deliveryDateTime,
            local_dt=localTime,
            platform='Rekki',
            order_id=order['reference'],
            customer_name=order['customer_account_no'],
            quantity=item['quantity'],
            item_name=item['name'],
            notes=order['notes'],
            customer_rank=customerRank.get(order['customer_account_no'], '')
        )

for order in orders['marketman']:
    # Convert Marketman UTC timestamp string to local time datetime object
    deliveryDateTime = marketman.get_delivery_dt(order)
    for item in order['Items']:
        ssData = google_sheets.add_order_to_sheet_data(
            ss_data=ssData,
            delivery_dt=deliveryDateTime,
            local_dt=localTime,
            platform='Marketman',
            order_id=order['OrderNumber'],
            customer_name=order['BuyerName'],
            quantity=item['Quantity'],
            item_name=item['ItemName'],
            notes=order['Comments'],
            customer_rank= customerRank.get(order['BuyerName'], '')
        )

for order in orders['notch']:
    deliveryDateTime, notes = notch.get_delivery_dt(order, localTime)
    ssData = google_sheets.add_order_to_sheet_data(
        ss_data=ssData,
        delivery_dt=deliveryDateTime,
        local_dt=localTime,
        platform='Notch',
        order_id=order['id'],
        customer_name=order['customer'],
        quantity='',
        item_name=order['order url'],
        notes=notes,
        customer_rank=customerRank.get(order['customer'], '')
    )

# Save the orders in the Google Spreadsheet
google_sheets.update_sheet_tabs(ssData)

# Create Estimates in QuickBooks
for order in orders['shopify']:
    lineItems = []
    for line in order['line_items']:
        discount = Decimal("0")
        for discount_allocation in line['discount_allocations']:
            discount += Decimal(discount_allocation['amount'])
        lineItems.append(
            quickbooks.prepare_qb_line_item(
                platform='Shopify',
                item_name_in_order=line['name'],
                price=Decimal(str(line['price'])),
                qty=Decimal(line['quantity']),
                discount=discount,
                logger=logger,
                application_path=application_path
            )
        )
    quickbooks.create_qb_estimate(
        platform='Shopify',
        customer_name_in_order=(order['customer']['first_name'] + ' ' + order['customer']['last_name']).strip(),
        line_items=lineItems,
        order_number=order['id'],
        logger=logger,
        application_path=application_path
    )

for order in orders['rekki']:
    lineItems = []
    for line in order['items']:
        lineItems.append(
            quickbooks.prepare_qb_line_item(
                platform='Rekki',
                item_name_in_order=line['name'],
                price=Decimal(str(line['price']) + '.' + str(line['price_cents'])),
                qty=Decimal(line['quantity']),
                discount=Decimal("0"),
                logger=logger,
                application_path=application_path
            )
        )
    quickbooks.create_qb_estimate(
        platform='Rekki',
        customer_name_in_order=order['contact_name'],
        line_items=lineItems,
        order_number=order['reference'],
        logger=logger,
        application_path=application_path
    )

for order in orders['marketman']:
    lineItems = []
    for line in order['Items']:
        lineItems.append(
            quickbooks.prepare_qb_line_item(
                platform='Marketman',
                item_name_in_order=line['ItemName'],
                price=Decimal(str(line['Price'])),
                qty=Decimal(line['Quantity']),
                discount=Decimal("0"),
                logger=logger,
                application_path=application_path
            )
        )
    quickbooks.create_qb_estimate(
        platform='Marketman',
        customer_name_in_order=order['BuyerName'],
        line_items=lineItems,
        order_number=order['OrderNumber'],
        logger=logger,
        application_path=application_path
    )
