import requests
import os

def send_discord(message):
    webhook = os.environ["DISCORD_WEBHOOK_URL"]

    requests.post(
        webhook,
        json={"content": message}
    )