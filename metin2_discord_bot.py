import os
import requests
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime

# ===== CONFIG =====
BOARD_URL = os.getenv("THREAD_URL")  # acum board-ul Item Shop
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # secunde
STATE_FILE = "last_post.json"
headers = {"User-Agent": "Mozilla/5.0"}
# ==================

def get_last_saved_post():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_post_id")
    except:
        return None

def save_last_post(post_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_post_id": post_id}, f)

# 1️⃣ Extrage thread-uri din board
def fetch_threads():
    try:
        r = requests.get(BOARD_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Eroare la fetch board:", e)
        return []

    threads = []
    # selector CSS pentru link thread (a.subject)
    for a in soup.select("a.subject"):
        thread_url = a.get("href")
        if thread_url.startswith("http"):
            threads.append(thread_url)
        else:
            # forum-ul folosește link relativ
            threads.append("https://board.ro.metin2.gameforge.com/" + thread_url)
    return threads

# 2️⃣ Extrage ultimul post dintr-un thread
def fetch_last_post(thread_url):
    try:
        r = requests.get(thread_url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Eroare la fetch thread:", e)
        return None

    articles = soup.find_all("article")
    if not articles:
        return None

    last_article = articles[-1]
    post_id = last_article.get("id")
    content_div = last_article.find("div", class_="messageText")
    if post_id and content_div:
        content = content_div.get_text(separator="\n").strip()
        return {"id": post_id, "content": content, "url": thread_url + "#" + post_id}
    return None

# 3️⃣ Trimite la Discord
def send_to_discord(content, post_id):
    data = {
        "username": "Metin2 Board Bot",
        "embeds": [{
            "title": "📢 Postare nouă pe forum!",
            "description": content[:4000],
            "url": THREAD_URL + "#" + post_id,
            "color": 16711680,
            "footer": {"text": "Metin2 România"},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    try:
        r = requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        print("Discord status:", r.status_code)
    except Exception as e:
        print("Eroare la Discord webhook:", e)

# ===== Main Loop =====
def main():
    if not BOARD_URL or not DISCORD_WEBHOOK:
        print("Lipsesc variabilele de mediu!")
        return

    print("Bot pornit...")
    last_saved_id = get_last_saved_post()

    # la prima rulare, salvează ultimul post ca referință
    if not last_saved_id:
        threads = fetch_threads()
        for thread in threads:
            post = fetch_last_post(thread)
            if post:
                last_saved_id = post["id"]
        if last_saved_id:
            save_last_post(last_saved_id)

    while True:
        try:
            threads = fetch_threads()
            new_posts = []
            for thread in threads:
                post = fetch_last_post(thread)
                if post and post["id"] != last_saved_id:
                    new_posts.append(post)

            if new_posts:
                print(f"Gasit {len(new_posts)} postări noi.")
                for post in reversed(new_posts):
                    send_to_discord(post["content"], post["id"])
                    save_last_post(post["id"])
                    last_saved_id = post["id"]
            else:
                print("Nicio postare noua.")

            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("Oprire la cerere...")
            break
        except Exception as e:
            print("Eroare neașteptată:", e)
            time.sleep(30)

if __name__ == "__main__":
    main()
