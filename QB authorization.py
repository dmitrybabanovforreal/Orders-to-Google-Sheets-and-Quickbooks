#! /usr/bin/python3
import base64, json, os, datetime

from flask import Flask, request, redirect
import requests

import config

app = Flask(__name__)

@app.route(config.qb_auth_slug)
def authorization():
    # Check if user returned from the authorization page with the code
    authCode = request.args.get('code')
    if authCode:
        # send the code to get the token
        headers = {
            'Accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + str(base64.b64encode((config.qb_id + ':' + config.qb_secret).encode("utf-8")), "utf-8")
        }
        payload = {
            'code': authCode,
            'redirect_uri': config.qb_redirect_uri + config.qb_auth_slug,
            'grant_type': 'authorization_code'
        }
        response = requests.post(f'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer', data=payload, headers=headers)

        variables = json.load(open('variables.txt', 'r'))
        variables['quickbooks']['access token'] = response.json()['access_token']
        variables['quickbooks']['refresh token'] = response.json()['refresh_token']
        # Add almost an hour to account for slow requests speed:
        variables['quickbooks']['best before'] = (
                    datetime.datetime.utcnow() + datetime.timedelta(seconds=3300)).isoformat()

        json.dump(variables, open('variables.txt', 'w'))  # Save them immediately

        return f'\n\nThe app is authorized, thank you.\n\nYou can close this tab now.'

    else:
        # send the authorization request to get the code
        redirectUrl = f'https://appcenter.intuit.com/app/connect/oauth2/authorize?' \
                      f'scope={config.qb_scope}&' \
                      f'client_id={config.qb_id}&' \
                      f'response_type=code&' \
                      f'redirect_uri={config.qb_redirect_uri}{config.qb_auth_slug}&' \
                      f'state=ProductionAuth'
        return redirect(redirectUrl)

@app.route('/')
def hello_world():
    return 'Hello World!'
