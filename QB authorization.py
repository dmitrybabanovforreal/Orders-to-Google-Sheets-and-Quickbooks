#! /usr/bin/python3

from flask import Flask, request, redirect
import config, requests, base64, json

app = Flask(__name__)

@app.route(config.authSlug)
def authorization():
    # check if user returned from the authorization page with the code
    authCode = request.args.get('code')
    if authCode:
        # send the code to get the token
        headers = {
            'Accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + str(base64.b64encode((config.id + ':' + config.secret).encode("utf-8")), "utf-8")
        }
        payload = {
            'code': authCode,
            'redirect_uri': config.redirect_uri + config.authSlug,
            'grant_type': 'authorization_code'
        }
        response = requests.post(f'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer', data=payload, headers=headers)

        json.dump(response.json(), open('response QB.json', 'w'))

        return f'\n\nThe app is authorized, thank you.\n\nYou can close this tab now.'

    else:
        # send the authorization request to get the code
        redirectUrl = f'https://appcenter.intuit.com/app/connect/oauth2/authorize?' \
                      f'scope={config.scope}&' \
                      f'client_id={config.id}&' \
                      f'response_type=code&' \
                      f'redirect_uri={config.redirect_uri}{config.authSlug}&' \
                      f'state=ProductionAuth'
        return redirect(redirectUrl)

@app.route('/')
def hello_world():
    return 'Hello World!'
