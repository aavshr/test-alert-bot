import hashlib
import hmac
import os
import random
import string

import flask
import requests

_TELEGRAM_API_URL = f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}"
_TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
_MESSAGE = os.environ["MESSAGE"]
_TWITCH_BROADCASTER_LOGIN = os.environ["TWITCH_BROADCASTER_LOGIN"]
_TWITCH_ID = os.environ["TWITCH_ID"]
_TWITCH_SECRET = os.environ["TWITCH_SECRET"]
_TWITCH_TOKEN_URL = (
    "https://id.twitch.tv/oauth2/token?client_id={}"
    "&client_secret={}&grant_type=client_credentials"
).format(_TWITCH_ID, _TWITCH_SECRET)
_TWITCH_API_URL = "https://api.twitch.tv/helix/"
_TWITCH_EVENTSUB_SECRET = "".join(
    random.choices(string.ascii_letters + string.digits, k=16)
)


app = flask.Flask(__name__)


def _check_signature(headers: dict[str, str], body: str) -> bool:
    hmac_message = (
        headers["Twitch-Eventsub-Message-Id"]
        + headers["Twitch-Eventsub-Message-Timestamp"]
        + body
    )
    signature = hmac.new(
        bytes(_TWITCH_EVENTSUB_SECRET, "utf-8"),
        bytes(hmac_message, "utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return headers["Twitch-Eventsub-Message-Signature"] == "sha256=" + signature


@app.route("/webhook")
def handle_twitch_webhook():
    headers = {key: value for key, value in flask.request.headers.items()}
    if not _check_signature(headers, flask.request.data):
        return flask.Response(status=403)

    req: dict = flask.request.json

    if req.get("challenge"):
        return flask.make_response(req["challenge"])

    body = {
        "chat_id": _TELEGRAM_CHAT_ID,
        "text": _MESSAGE.format(**req["event"]),
        "parse_mode": "html",
    }
    requests.post(_TELEGRAM_API_URL, json=body)

    return flask.Response(status=201)


@app.route("/setup")
def handle_setup():
    with requests.Session() as session:
        resp = session.post(_TWITCH_TOKEN_URL)
        if resp.status_code != 200:
            return flask.make_response(
                f"Can't get twitch access token. Error: {resp.text}", 418
            )
        token = resp.json()["access_token"]

        session.headers["client-id"] = _TWITCH_ID
        session.headers["authorization"] = f"Bearer {token}"
        session.headers["content-type"] = "application/json"

        resp = session.get(f"{_TWITCH_API_URL}users?login={_TWITCH_BROADCASTER_LOGIN}")
        broadcaster_id = resp.json()["data"][0]["id"]

        body = {
            "type": "stream.online",
            "version": 1,
            "condition": {"broadcaster_user_id": broadcaster_id},
            "transport": {
                "method": "webhook",
                "callback": f"{flask.request.url_root}webhook",
                "secret": _TWITCH_EVENTSUB_SECRET,
            },
        }
        session.post(f"{_TWITCH_API_URL}eventsub/subscriptions", json=body)

    return flask.make_response("Twitch webhooks have been successfully installed.")
