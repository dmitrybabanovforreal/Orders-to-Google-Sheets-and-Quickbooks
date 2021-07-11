import requests, os, logging, traceback, datetime, json, imaplib, email, csv, ezsheets, base64
from dateutil import tz
import config

def get_token():
    # This function updates the access token if it expired and then returns it
    if datetime.datetime.utcnow() > datetime.datetime.fromisoformat(variables['quickbooks']['best before']):
        url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
        headers = {
            'Accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + str(base64.b64encode((config.id + ':' + config.secret).encode("utf-8")), "utf-8")
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

    return variables['quickbooks']['access token']


application_path = os.path.abspath(os.path.dirname(__file__))
user_path = application_path
localTime = datetime.datetime.utcnow().replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz('America/Toronto'))

# Create the logs folder if it's not created yet
logsFolderName = 'logs for the past 20 days'
logsPath = os.path.join(application_path, logsFolderName)
if logsFolderName not in os.listdir(application_path):
    os.mkdir(logsPath)

# Create the logging object
reportName = os.path.join(logsPath, 'log ' + localTime.strftime('%Y-%m-%d %H-%M-%S') + '.txt')
logging.basicConfig(filename=reportName, level=logging.INFO, format=' %(asctime)s -  %(levelname)s -  %(message)s')

# Remove the old logs
for fileName in os.listdir(logsPath):
    try:
        logDate = datetime.datetime.strptime(fileName[4:-4], '%Y-%m-%d %H-%M-%S')
        if logDate < (localTime - datetime.timedelta(days=20)):
            os.remove(os.path.join(logsPath, fileName))
    except:
        continue

########################################################################################################################
# 1. Obtain the orders data
########################################################################################################################
# Open or create a new file with system variables
parameters = json.load(open(os.path.join(application_path, 'parameters.txt'), 'r'))

# Open or create a new file with system variables
if 'variables.txt' not in os.listdir(application_path):
    variables = {
        'shopify': {
            'last order id': 0,
        },
        'rekki': {
            'last order time': '2021-07-01T00:00:00.000000Z',
            'last orders': [],  # ids of the previous import
        },
        'marketman': {
            'last order time': None,
            'last orders': [],  # ids of the previous import
        },
        'notch': {
            'last orders': [],  # ids of the last 100 orders
        },
        'quickbooks': {
            'access token': '',
            'refresh token': '',
            'best before': datetime.datetime(2021, 7, 1, 0, 0, 0).isoformat(),  # UTC time
        }
    }
else:
    variables = json.load(open(os.path.join(application_path, 'variables.txt'), 'r'))

orders = {}

# Get orders from Shopify
# API reference https://shopify.dev/docs/admin-api/rest/reference/orders/order#index-2021-04
shop = parameters['shopify']['store']
url = f'https://{shop}.myshopify.com/admin/api/2021-04/orders.json'
headers = {'X-Shopify-Access-Token': parameters['shopify']['token']}
params = {
    'status': 'open',
    'limit': 250,
    'since_id': variables['shopify']['last order id'],
    'created_at_min': '2021-07-01T00:00:00-07:00'
}
response = requests.get(url, params=params, headers=headers)
try:
    response.raise_for_status()
except:
    logging.error(traceback.format_exc())

orders['shopify'] = response.json()['orders']

# Continue requesting next pages if there are any
while response.headers.get('Link'):
    url = response.headers.get('Link')
    headers = {'X-Shopify-Access-Token': parameters['shopify']['token']}
    params = {
        'status': 'open',
        'limit': 250,
        'since_id': variables['shopify']['last order id'],
        'created_at_min': '2021-07-01T00:00:00-07:00'
    }
    response = requests.get(url, params=params, headers=headers)
    try:
        response.raise_for_status()
    except:
        logging.error(traceback.format_exc())

    orders['shopify'].append(response.json()['orders'])

logging.info(f'Shopify returned {str(len(orders["shopify"]))} orders')

# Find the last id in the list
for order in orders['shopify']:
    if int(order['id']) > variables['shopify']['last order id']:
        variables['shopify']['last order id'] = int(order['id'])

# Get orders from Rekki
# API reference https://api.rekki.com/swagger/index.html#operations-orders-ListOrdersBySupplierV3
url = 'https://api.rekki.com/api/integration/v3/orders/list'
headers = {
    'Authorization': 'Bearer ' + parameters['rekki']['token'],
    'X-REKKI-Authorization-Type': 'supplier_api_token',
}
params = {
    'since': variables['rekki']['last order time'],  # Comes as a string from the previous API call
    "skip_integrated": False
}
response = requests.post(url, json=params, headers=headers)
try:
    response.raise_for_status()
except:
    logging.error(traceback.format_exc())

# Remove orders that may duplicate from the last call and save the last order's timestamp
orders['rekki'] = []
orderIds = []
for order in response.json()['orders']:
    currentOrderDateTimeObj = datetime.datetime.strptime(order['inserted_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
    latestOrderDateTimeObj = datetime.datetime.strptime(variables['rekki']['last order time'], '%Y-%m-%dT%H:%M:%S.%fZ')
    if currentOrderDateTimeObj > latestOrderDateTimeObj:
        variables['rekki']['last order time'] = order['inserted_at']

    if order['reference'] not in variables['rekki']['last orders']:
        orders['rekki'].append(order)
        orderIds.append(order['reference'])

variables['rekki']['last orders'] = orderIds

logging.info(f'Rekki returned {str(len(orders["rekki"]))} orders')

# Get orders from Marketman
# API reference https://api-doc.marketman.com/?version=latest#3ade36ea-af67-4dc0-842b-eca56311d1e0
# Get the token first
url = "https://api.marketman.com/v3/buyers/auth/GetToken"
payload = {
  "APIKey": f"{parameters['marketman']['api key']}",
  "APIPassword": f"{parameters['marketman']['api password']}"
}
response = requests.post(url, json=payload)
try:
    response.raise_for_status()
except:
    logging.error(traceback.format_exc())
accessToken = response.json()['Token']

# Get the orders since the last order time
# todo Obtain the API credentials and try to look into vendors and buyers orders, save the vendors/buyers ID
url = "https://api.marketman.com/v3/vendors/orders/GetOrdersByDeliveryDate"
payload = {
    "DateTimeFromUTC": localTime.strftime('%Y/%m/%d 00:00:00'),
    "VendorGuid": parameters['marketman']['vendor guid']
}
headers = {
      'AUTH_TOKEN': f'{accessToken}'
    }
response = requests.post(url, headers=headers, json=payload)
try:
    response.raise_for_status()
except:
    logging.error(traceback.format_exc())

# Remove orders that may duplicate from the last call
orders['marketman'] = []
orderIds = []
for order in response.json()['Orders']:
    if order['OrderNumber'] not in variables['marketman']['last orders']:
        orders['marketman'].append(order)
        orderIds.append(order['OrderNumber'])
variables['marketman']['last orders'] = orderIds

logging.info(f'Marketman returned {str(len(orders["marketman"]))} orders')

# Get orders from NotchOrdering
orders['notch'] = []
# Read the emails from the last email
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(parameters['notch']['gmail email'], parameters['notch']['gmail password'])
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
    if parameters['notch']['notification from address'] in msg['from'] and 'order ' in msg['subject']:
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
            'delivery date': body.split('Delivery day:')[1].split('\n')[0].strip(),  # format Saturday, 19 June 2021
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
    orders['notch'].append(order)
    variables['notch']['last orders'] = variables['notch']['last orders'][-99:] + [order['id']]  # save the last 100 order IDs

json.dump(variables, open(os.path.join(application_path, 'variables.txt'), 'w'))

########################################################################################################################
# 2. Process and output the data
########################################################################################################################

# Load the dictionary to match Rekki product codes with the ones from Shopify
data = list(csv.reader(open('shopify-rekki product codes matching.csv')))
productCodes = {}
for row in data:
    productCodes[row[0]] = row[1]  # the first item is Rekki, the second one is Shopify

# Replace the Rekki product code using the productCodes dict
for order in orders['rekki']:
    for item in order['items']:
        try:
            item['product_code'] = productCodes[item['product_code']]
        except:
            continue

# Load the dictionary with the location info per each product
data = list(csv.reader(open('product codes location.csv')))
productLocation = {}
for row in data:
    productLocation[row[0]] = row[1]  # the first item is product code, the second one is location

# Load the dictionary with the customer rank info
data = list(csv.reader(open('customer rank.csv')))
customerRank = {}
for row in data:
    customerRank[row[0]] = row[1]  # the first item is customer ID, the second one is rank int()

# todo Add the location information using the productLocation dictionary

# Save the orders in the Google Spreadsheet
ss = ezsheets.Spreadsheet(parameters['google_sheet_id'])  # Spreadsheet ID from its URL
ssData = {}
qbData = []

for sheet in ss.sheets:
    # Remove the tabs older than today
    try:
        if datetime.datetime.strptime(sheet.title, '%a, %b %d %Y') < localTime - datetime.timedelta(days=1):
            sheet.delete()
        else:
            rows = []
            # Get not empty rows only
            for row in sheet.getRows():
                if True in (elem != '' for elem in row):
                    rows.append(row)
            ssData[sheet.title] = rows
    except:
        # If sheet title is not a date, don't process it as all
        continue

# Add the orders with delivery date starting from today to the spreadsheet dict and quickbooks dict
for order in orders['shopify']:
    for item in order['items']:
        # todo find out where to get the delivery date from on Shopify
        pass

for order in orders['rekki']:
    deliveryDateTime = datetime.datetime.strptime(order['delivery_on'], '%Y-%m-%d')
    if deliveryDateTime < localTime - datetime.timedelta(days=1):
        # If delivery date is older than today, skip this order
        continue
    else:
        # If there is no sheet for this delivery date yet, create it
        sheetTitle = deliveryDateTime.strftime('%a, %b %d %Y')
        ssData.setdefault(sheetTitle, [])
    # todo Obtain the customer ID and name
    qbItem = {
        'CustomerRef': {
            'value': ''  # the ID of the Customer
        },
        'Line': []
    }
    for item in order['items']:
        ssData[sheetTitle].append([
            'Rekki',
            order['reference'],
            order['customer_account_no'],
            item['quantity'],
            item['name'],
            order['notes'],
            customerRank[order['customer_account_no']]
        ])
        qbItem['Line'].append({
            'Id': '',
            'DetailType': 'SalesItemLineDetail',
            'Amount': 1,
            'Description': '',
            'SalesItemLineDetail': {}
        })
    qbData.append(qbItem)

for order in orders['marketman']:
    # Convert Marketman UTC timestamp string to local time datetime object
    deliveryDateTime = datetime.datetime.strptime(order['DeliveryDateUTC'], '%Y-%m-%d').replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz('America/Toronto'))
    if deliveryDateTime < localTime - datetime.timedelta(days=1):
        # If delivery date is older than today, skip this order
        continue
    else:
        # If there is no sheet for this delivery date yet, create it
        sheetTitle = deliveryDateTime.strftime('%a, %b %d %Y')
        ssData.setdefault(sheetTitle, [])
    for item in order['Items']:
        ssData[sheetTitle].append([
            'Marketman',
            order['OrderNumber'],
            order['BuyerName'],  # todo check that customers name is in Buyer name and not Vendor name
            item['Quantity'],
            item['ItemName'],
            order['Comments'],
            customerRank[order['BuyerName']]  # todo check that customers name is in Buyer name and not Vendor name
        ])

for order in orders['notch']:
    try:
        deliveryDateTime = datetime.datetime.strptime(order['delivery date'], '%A, %d %B %Y')
        notes = "'"
    except:
        deliveryDateTime = localTime
        notes = '[ERROR] CHECK THE DELIVERY DATE, IT MAY BE INCORRECT'
    if deliveryDateTime < localTime - datetime.timedelta(days=1):
        # If delivery date is older than today, skip this order
        continue
    else:
        # If there is no sheet for this delivery date yet, create it
        sheetTitle = deliveryDateTime.strftime('%a, %b %d %Y')
        ssData.setdefault(sheetTitle, [])
    ssData[sheetTitle].append([
        'Notch',
        order['id'],
        order['customer'],
        '',
        order['order url'],
        notes,
        customerRank[order['customer']]
    ])

# Sort each spreadsheet's rows by customer rank/priority and add headers to the first row
for tab in ssData.keys():
    rows = ssData[tab]
    rows.sort(key=lambda x:x[6])  # sort by the 7th column (customer rank)
    rows = [[
        'Platform',
        'Order',
        'Customer',
        'Item Qty',
        'Item Name',
        'Notes',
        'Priority'
    ]] + rows  # add headers to the beginning
    ssData[tab] = rows

# Sort sheets by date using a datetime object made from tab names
tabsOrder = []
for key in ssData.keys():
    tabsOrder.append([
        datetime.datetime.strptime(key, '%a, %b %d %Y'),
        key
    ])
tabsOrder.sort()

# Remove old sheets and add new ones
ss.createSheet('[none]', 0)  # Create an empty sheet because you can't leave zero sheets
for sheet in ss.sheets[1:]:
    sheet.delete()
len(ss.sheets)

for item in tabsOrder:
    tabName = item[1]
    sheet = ss.createSheet(tabName)
    sheet.updateRows(ssData[tabName])

ss.sheets[0].delete()  # Remove the empty sheets

# Create Sales Orders in QuickBooks
# Authorization API reference: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/faq
# Estimate API reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/estimate

# todo Create an estimate for each order
