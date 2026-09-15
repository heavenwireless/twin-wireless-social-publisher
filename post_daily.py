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
    # Rewritten 2026-09-07 at Murad's direction: "no educational posts",
    # and a promotional voice rather than teaching - emoji-forward,
    # expertise-first, short, always a reason to come in, no how-to.
    #
    # The Monday caption previously read "We repair it same day". That is a
    # turnaround promise, which the knowledge base forbids outright, and it had
    # been publishing weekly. Removed. Nothing here promises a timeframe.
    #
    # Image filenames are unchanged, so each caption still matches its picture.
    # NOTE: there is no smartwatch slot because there is no smartwatch image -
    # adding one needs a new PNG in images/, not just a caption.
    0: (
        "mon-cracked-screen-price.png",
        "📱✨ Cracked screen? We replace them every day, and we'll tell you "
        "exactly what yours needs before anything is done. Stop by 2328 Line Ave, "
        "Shreveport. 🛠️ (318) 670-3938",
    ),
    1: (
        "tue-android-repair.png",
        "🤖🛠️ Screens, batteries, charging ports - we have the "
        "expertise to diagnose and repair your Android device. Samsung, Google, "
        "Motorola and more. Free diagnosis. 💬 (318) 670-3938",
    ),
    2: (
        "wed-computer-laptop.png",
        "🔝🖥️ Every computer is different, so we take the time to "
        "evaluate each one properly rather than guessing. Bring yours to Line Ave "
        "for a free diagnosis. 🌟 (318) 670-3938",
    ),
    3: (
        "thu-game-console.png",
        "⚡️🎮 Console acting up? Bring it to us and get back in the "
        "game. PlayStation, Xbox and Switch. 👨‍🔧 "
        "(318) 670-3938",
    ),
    4: (
        "fri-back-glass.png",
        "💎🔧 Shattered back glass doesn't mean a new phone. We handle "
        "it - bring it in and we'll confirm the exact price after inspection. "
        "💬 2328 Line Ave, Shreveport. (318) 670-3938",
    ),
    5: (
        "sat-prepaid-activation.png",
        "📲✅ New phone? We'll get you activated. Simple Mobile, AT&T "
        "Prepaid, Cricket and Verizon Prepaid - bring the phone with you. Open "
        "9AM-8PM. 💬 2328 Line Ave, Shreveport.",
    ),
    6: (
        "sun-tablet-accessories.png",
        "💻✅ From hardware to software, we handle tablet repair - iPad and "
        "Android alike. Screen protectors and cases too. Open 11AM-5PM today. "
        "🛡️ 2328 Line Ave, Shreveport.",
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


def lint_caption(caption):
    """Brand guard, added 2026-09-08 at Murad's direction ("can we add the
    brand check to it and keep it going"). Mirrors the rules the TwinSocial
    publisher enforces in brand.mjs -- this script previously ran no checks at
    all, which is how a banned same-day promise got published weekly for a
    month. Returns a list of problems; empty means clean.

    The captions here are static, so in practice this trips only when someone
    edits CONTENT above and reintroduces a banned claim. That is exactly the
    moment it needs to trip.
    """
    import re

    problems = []
    lower = caption.lower()

    # Turnaround must never be an unconditional promise. "Most repairs same
    # day" is the one approved hedge.
    if re.search(r"same[- ]day", lower) and not re.search(
        r"\b(most|many|majority|usually|often|typically|generally)\b[^.]{0,40}same[- ]day"
        r"|same[- ]day\b[^.]{0,40}\b(for|on|in) most\b",
        lower,
    ):
        problems.append("unhedged same-day promise")

    for banned in (
        "match or beat",       # price-match claim, banned outright
        "cheapest guaranteed",
        "best in louisiana",
        "we repair everything",
        "paypal",              # bill pay settles via Cash App/Zelle only
        "authorized apple", "apple authorized", "apple certified",
        "genuine apple", "apple partner",
        "twin iptv",
    ):
        if banned in lower:
            problems.append(f"banned claim: {banned!r}")

    # Any dollar figure must be one of the published prices.
    for price in re.findall(r"\$(\d+(?:\.\d{2})?)", caption):
        if price not in {"29.99", "40", "50", "60", "80", "100", "150"}:
            problems.append(f"price ${price} is not on the published list")

    return problems


APPROVAL_API = "https://www.twin-wireless.com/api/content-approvals.php"
# Weekly rotation, so approvals are keyed to a fixed pseudo-date rather than a
# calendar day: approving Tuesday's creative once keeps Tuesday running until
# its caption or image changes.
ROTATION_KEY = "0000-00-00"


def rotation_fingerprint(image_path: str, caption: str) -> str:
    """Same shape as the JS publisher's: image BYTES plus the exact caption.

    Hashing the bytes, not the filename, is what makes "material changes
    invalidate approval" true here -- swapping the PNG behind an unchanged
    filename produces a different fingerprint and the day falls back to held.
    """
    import hashlib

    h = hashlib.sha256()
    with open(image_path, "rb") as fh:
        h.update(hashlib.sha256(fh.read()).hexdigest().encode())
    h.update(b"caption:")
    h.update(caption.encode("utf-8"))
    return h.hexdigest()[:24]


def owner_approved(item_id: str, fingerprint: str) -> tuple[bool, str]:
    """Owner approval check. FAILS CLOSED on every uncertainty.

    Added 2026-09-15. Until then this cron published to Facebook and Instagram
    every day with no approval gate at all -- only the brand lint. Murad's
    standing requirement is that he approves content before it publishes, and
    "verify EVERY publisher consumes owner approval": a gate in the JavaScript
    publisher says nothing about this one, which is a separate service on a
    separate schedule reaching the same two public accounts.
    """
    secret = os.environ.get("CONTENT_APPROVAL_SECRET", "").strip()
    if not secret:
        return False, "CONTENT_APPROVAL_SECRET is not set"
    try:
        resp = requests.get(
            APPROVAL_API,
            params={"date": ROTATION_KEY},
            headers={"X-Approval-Secret": secret},
            timeout=20,
        )
        if resp.status_code != 200:
            return False, f"approval API HTTP {resp.status_code}"
        store = resp.json().get("approvals") or {}
    except Exception as exc:  # network, DNS, TLS, bad JSON -- all fail closed
        return False, f"approval API unreachable: {exc}"

    rec = store.get(item_id) if isinstance(store, dict) else None
    if not isinstance(rec, dict) or rec.get("approved") is not True:
        return False, "not approved by owner"
    if rec.get("fingerprint") != fingerprint:
        return False, "content changed since it was approved"
    return True, f"approved by {rec.get('approvedBy')} at {rec.get('approvedAt')}"


def main():
    weekday = datetime.now(ZoneInfo("America/Chicago")).weekday()
    filename, caption = CONTENT[weekday]
    image_path = os.path.join(os.path.dirname(__file__), "images", filename)

    problems = lint_caption(caption)
    if problems:
        # Fail closed: better a missed day than a banned claim published.
        raise SystemExit(
            f"BRAND CHECK FAILED for weekday {weekday} -- not posting: {problems}"
        )

    item_id = f"rotation-{weekday}"
    fingerprint = rotation_fingerprint(image_path, caption)
    ok, why = owner_approved(item_id, fingerprint)
    print(f"Approval check: {item_id} fp={fingerprint} -> {'RELEASE' if ok else 'HELD'} ({why})")
    if not ok:
        # Exit 0, not a failure: being held is the correct, expected outcome
        # for unapproved content, and a red cron run every day would train
        # everyone to ignore this job's status.
        print("HELD -- nothing posted. Approve this creative to release it.")
        return

    post_to_facebook(image_path, caption)
    post_to_instagram(filename, caption)


if __name__ == "__main__":
    main()
