from typing import List, Dict, Tuple
from logging import getLogger
import json, os, traceback, imaplib, email, datetime

import config


def get_orders(logger: getLogger, application_path: str) -> List:
    orders = []
    try:
        variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))

        # Read the emails from the last email
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(config.notch_gmail_address, config.notch_gmail_password)
        mail.select('inbox')

        data = mail.search(None, 'ALL')
        mail_ids = data[1]
        id_list = mail_ids[0].split()
        latest_email_id = int(id_list[-1])

        i = 0
        for emailId in range(latest_email_id, 1, -1):
            data = mail.fetch(str(emailId), '(RFC822)')
            for response_part in data:
                arr = response_part[0]
                if isinstance(arr, tuple):
                    msg = email.message_from_string(str(arr[1], 'utf-8'))
                    break
            if config.notch_notifications_from_address in msg['from'] and 'order ' in msg['subject']:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":  # ignore attachments/html
                        body = part.get_payload(decode=True).decode('utf-8')
                        break
            else:
                continue
            try:
                order = {
                    'id': body.split('Order ID:')[1].split('\n')[0].strip(),
                    # 'order date': body.split('Order place date:')[1].split('\n')[0].strip(),  # format Friday, 18 June 2021
                    'delivery date': body.split('Delivery day:')[1].split('\n')[0].strip(),
                    # format Saturday, 19 June 2021
                    'customer': body.split('Made by:')[1].split('\n')[0].strip(),
                    'order url': body.split('View order details')[1].split('Don')[0].strip().strip('<>'),
                    # 'shipping address': body.split('Shipping Address:')[1].split('\n')[0].strip()
                }
            except:
                order = {
                    'id': msg['subject'].split('(#')[1].split(')')[0].strip(),
                    # 'order date': 'Monday, 1 January 1990',
                    'delivery date': 'Monday, 1 January 1990',
                    'customer': '[ERROR] CHECK THE ORDER NOTIFICATION, IT FAILED TO PROCESS',
                    'order url': 'https://www.notchordering.com/'
                    # 'shipping address': body.split('Shipping Address:')[1].split('\n')[0].strip()
                }
            # Stop if iterated over 5 orders from the previous imports in a row
            if order['id'] in variables['notch']['last orders']:
                i += 1
                if i == 5:
                    break
                else:
                    continue
            i = 0
            orders.append(order)
            variables['notch']['last orders'] = variables['notch']['last orders'][-99:] + [
                order['id']]  # save the last 100 order IDs

        json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))
    except:
        logger.error(f'Could n\'t get orders from Notch:')
        logger.error(traceback.format_exc())

    return orders


def get_delivery_dt(order: Dict, local_dt: datetime.datetime) -> Tuple[datetime.datetime, str]:
    try:
        delivery_date_time = datetime.datetime.strptime(order['delivery date'], '%A, %d %B %Y')
        notes = "'"
    except:
        delivery_date_time = local_dt
        notes = '[ERROR] CHECK THE DELIVERY DATE, IT MAY BE INCORRECT'

    return delivery_date_time, notes