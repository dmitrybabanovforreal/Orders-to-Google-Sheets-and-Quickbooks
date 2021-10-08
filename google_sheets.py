import datetime
from typing import List, Dict, Union

import ezsheets

import config


def get_sheet_data() -> Dict:
    ss = ezsheets.Spreadsheet(config.google_sheet_id)  # Spreadsheet ID from its URL
    ss_data = {}

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
                ss_data[sheet.title] = rows
        except:
            # If sheet title is not a date, don't process it as all
            continue

    return ss_data


def add_order_to_sheet_data(
        ss_data: Dict[str, List],
        delivery_dt: datetime.datetime,
        local_dt: datetime.datetime,
        platform: str,
        order_id: Union[str, int],
        customer_name: str,
        quantity: Union[str, int],
        item_name: str,
        notes: str,
        customer_rank: Union[str, int]
) -> Dict:
    if delivery_dt < local_dt - datetime.timedelta(days=1):
        return ss_data
    # If there is no sheet for this delivery date yet, create it
    sheet_title = delivery_dt.strftime('%a, %b %d %Y')
    ss_data.setdefault(sheet_title, [])
    ss_data[sheet_title].append([
        platform,
        order_id,
        customer_name,
        quantity,
        item_name,
        notes,
        customer_rank
    ])

    return ss_data


def update_sheet_tabs(ss_data: Dict[str, List]) -> None:
    ss = ezsheets.Spreadsheet(config.google_sheet_id)  # Spreadsheet ID from its URL

    # Sort each spreadsheet's rows by customer rank/priority and add headers to the first row
    for tab in ss_data.keys():
        rows = ss_data[tab]
        rows.sort(key=lambda x: x[6])  # sort by the 7th column (customer rank)
        rows = [[
            'Platform',
            'Order',
            'Customer',
            'Item Qty',
            'Item Name',
            'Notes',
            'Priority'
        ]] + rows  # add headers to the beginning
        ss_data[tab] = rows

    # Sort sheets by date using a datetime object made from tab names
    tabs_order = []
    for key in ss_data.keys():
        tabs_order.append([
            datetime.datetime.strptime(key, '%a, %b %d %Y'),
            key
        ])
    tabs_order.sort()

    # Remove old sheets and add new ones
    ss.createSheet('[none]', 0)  # Create an empty sheet because you can't leave zero sheets
    for sheet in ss.sheets[1:]:
        sheet.delete()
    len(ss.sheets)

    for item in tabs_order:
        tabName = item[1]
        sheet = ss.createSheet(tabName)
        sheet.updateRows(ss_data[tabName])

    ss.sheets[0].delete()  # Remove the dummy sheet
