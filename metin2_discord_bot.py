import os
import requests
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= CONFIG =================
BOARD_URL = os.getenv("THREAD_URL")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
STATE_FILE = "last_post.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
# =========================================

# ===== HTTP SESSION cu retry =====
session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[403, 429, 500, 502, 503, 504],
)
session.mount("https://", HTTPAdapter(max_retries=retry))


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"last_post_id": None}


def save_state(post_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_post_id": post_id}, f)


# ===== 1. Fetch THREAD-uri =====
def fetch_threads():
    try:
        r = session.get(BOARD_URL, headers=HEADERS, timeout=20)
    except Exception as e:
        print("❌ Eroare request board:", e)
        return []

    if len(r.text) < 5000:
        print("⚠️ HTML board prea mic (probabil blocat)")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    threads = []
    for a in soup.select("a.subject"):
        href = a.get("href")
        if not href:
            continue

        if href.startswith("http"):
            threads.append(href)
        else:
            threads.append("https://board.ro.metin2.gameforge.com/" + href)

    print(f"🔎 Thread-uri găsite: {len(threads)}")
    return threads


# ===== 2. Fetch ultimul POST din thread =====
def fetch_last_post(thread_url):
    try:
        r = session.get(thread_url, headers=HEADERS, timeout=20)
    except Exception as e:
        print("❌ Eroare request thread:", e)
        return None

    if len(r.text) < 5000:
        print("⚠️ HTML thread invalid:", thread_url)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    articles = soup.select("article")

    if not articles:
        return None

    last_article = articles[-1]
    post_id = last_article.get("id")

    content_div = last_article.select_one(".messageText")
    if not post_id or not content_div:
        return None

    content = content_div.get_text(separator="\n").strip()

    return {
        "id": post_id,
        "content": content,
        "url": thread_url + "#" + post_id,
    }


# ===== 3. Discord =====
def send_to_discord(post):
    data = {
        "username": "Metin2 Board Bot",
        "embeds": [
            {
                "title": "📢 Postare nouă pe Item Shop",
                "description": post["content"][:4000],
                "url": post["url"],
                "color": 15158332,
                "footer": {"text": "Metin2 România"},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
    }

    try:
        r = session.post(DISCORD_WEBHOOK, json=data, timeout=15)
        print("✅ Trimite Discord:", r.status_code)
    except Exception as e:
        print("❌ Eroare Discord:", e)


# ===== MAIN LOOP =====
def main():
    if not BOARD_URL or not DISCORD_WEBHOOK:
        print("❌ Variabilele de mediu lipsesc!")
        return

    print("🤖 Bot pornit...")
    state = load_state()
    last_post_id = state.get("last_post_id")

    # inițializare – NU trimite nimic la prima rulare
    if not last_post_id:
        print("📌 Inițializare stare...")
        threads = fetch_threads()
        for thread in threads:
            post = fetch_last_post(thread)
            if post:
                last_post_id = post["id"]
        if last_post_id:
            save_state(last_post_id)
        print("✅ Stare inițială salvată.")
        time.sleep(CHECK_INTERVAL)

    while True:
        try:
            threads = fetch_threads()
            new_posts = []

            for thread in threads:
                post = fetch_last_post(thread)
                if post and post["id"] != last_post_id:
                    new_posts.append(post)

            if new_posts:
                print(f"🔥 Postări noi: {len(new_posts)}")
                for post in reversed(new_posts):
                    send_to_discord(post)
                    save_state(post["id"])
                    last_post_id = post["id"]
            else:
                print("ℹ️ Nicio postare nouă.")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("⏹️ Oprire manuală.")
            break
        except Exception as e:
            print("❌ Eroare generală:", e)
            time.sleep(30)


if __name__ == "__main__":
    main()
