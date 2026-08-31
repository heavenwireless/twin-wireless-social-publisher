import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

PAGE_ID = os.environ["FB_PAGE_ID"]
PAGE_TOKEN = os.environ["FB_PAGE_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
GRAPH_VERSION = "v26.0"
RAW_IMAGE_BASE = (
    "https://raw.githubusercontent.com/heavenwireless/"
    "twin-wireless-social-publisher/main/images"
)

CONTENT = {
    0: (
        "mon-cracked-screen-price.png",
        "Cracked iPhone screen? We repair it same day at Twin Wireless -- see today's "
        "price on the board, call for other models. 2328 Line Ave, Shreveport. "
        "(318) 670-3938",
    ),
    1: (
        "tue-android-repair.png",
        "Android repair, done right. Screens, batteries, charging ports & more -- free "
        "diagnosis, real price on the spot. Samsung, Google, Motorola and other major "
        "Android brands. (318) 670-3938",
    ),
    2: (
        "wed-computer-laptop.png",
        "Laptop acting up? We repair computers too -- screens, batteries, hinges, slow "
        "performance and more. Bring it by Line Ave for a free diagnosis. "
        "(318) 670-3938",
    ),
    3: (
        "thu-game-console.png",
        "Console repair, handled right. PlayStation, Xbox and Switch repair -- call for "
        "a price. (318) 670-3938",
    ),
    4: (
        "fri-back-glass.png",
        "Cracked back glass? We fix that too. iPhone back glass from $100, confirmed "
        "after inspection. (318) 670-3938",
    ),
    5: (
        "sat-prepaid-activation.png",
        "New phone? Activated today. Simple Mobile, AT&T Prepaid, Cricket and Verizon "
        "Prepaid -- about 15 minutes with the phone in hand. Open 9AM-8PM, 2328 Line "
        "Ave, Shreveport.",
    ),
    6: (
        "sun-tablet-accessories.png",
        "Tablet repair, done right. iPad and tablet repair, plus screen protectors and "
        "cases. Open 11AM-5PM today. 2328 Line Ave, Shreveport.",
    ),
}


def post_to_facebook(image_path, caption):
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{PAGE_ID}/photos",
            data={"caption": caption, "access_token": PAGE_TOKEN},
            files={"source": f},
            timeout=60,
        )
    resp.raise_for_status()
    print(f"Facebook: posted successfully: {resp.json()}")


def post_to_instagram(filename, caption):
    image_url = f"{RAW_IMAGE_BASE}/{filename}"

    container_resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": PAGE_TOKEN,
        },
        timeout=60,
    )
    container_resp.raise_for_status()
    creation_id = container_resp.json()["id"]

    for _ in range(10):
        status_resp = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{creation_id}",
            params={"fields": "status_code", "access_token": PAGE_TOKEN},
            timeout=30,
        )
        status_resp.raise_for_status()
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram container failed: {status_resp.json()}")
        time.sleep(3)

    publish_resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": PAGE_TOKEN},
        timeout=60,
    )
    publish_resp.raise_for_status()
    print(f"Instagram: posted successfully: {publish_resp.json()}")


def main():
    weekday = datetime.now(ZoneInfo("America/Chicago")).weekday()
    filename, caption = CONTENT[weekday]
    image_path = os.path.join(os.path.dirname(__file__), "images", filename)

    post_to_facebook(image_path, caption)
    post_to_instagram(filename, caption)


if __name__ == "__main__":
    main()
