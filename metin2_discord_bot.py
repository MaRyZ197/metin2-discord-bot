import os
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import requests

# ================= CONFIG =================
BOARD_URL = os.getenv("THREAD_URL")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
STATE_FILE = "last_post.json"

# ================= HELPER =================
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"last_post_id": None}

def save_state(post_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_post_id": post_id}, f)

# ================= SELENIUM =================
def init_driver():
    options = Options()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver

def fetch_threads(driver):
    try:
        driver.get(BOARD_URL)
        time.sleep(5)  # așteaptă încărcarea JS
        threads = set()
        # toate <a> care conțin /thread/
        links = driver.find_elements(By.XPATH, '//a[contains(@href, "/thread/")]')
        for link in links:
            href = link.get_attribute("href")
            if href:
                threads.add(href)
        threads = list(threads)
        print(f"🔎 Thread-uri găsite: {len(threads)}")
        return threads
    except Exception as e:
        print("❌ Eroare Selenium fetch:", e)
        return []

def fetch_last_post(driver, thread_url):
    try:
        driver.get(thread_url)
        time.sleep(3)
        articles = driver.find_elements(By.TAG_NAME, "article")
        if not articles:
            return None
        last_article = articles[-1]
        post_id = last_article.get_attribute("id")
        content_div = last_article.find_element(By.CLASS_NAME, "messageText")
        content = content_div.text.strip()
        return {"id": post_id, "content": content, "url": thread_url + "#" + post_id}
    except Exception as e:
        print("❌ Eroare Selenium thread:", e)
        return None

# ================= DISCORD =================
def send_to_discord(post):
    payload = {
        "username": "Metin2 Board Bot",
        "embeds": [{
            "title": "📢 Postare nouă pe Item Shop",
            "description": post["content"][:4000],
            "url": post["url"],
            "color": 15158332,
            "footer": {"text": "Metin2 România"},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
        print("✅ Trimite Discord:", r.status_code)
    except Exception as e:
        print("❌ Eroare Discord:", e)

# ================= MAIN LOOP =================
def main():
    if not BOARD_URL or not DISCORD_WEBHOOK:
        print("❌ Lipsesc variabilele de mediu!")
        return

    print("🤖 Bot pornit...")
    state = load_state()
    last_post_id = state.get("last_post_id")

    driver = init_driver()

    # Inițializare
    if not last_post_id:
        print("📌 Inițializare stare...")
        threads = fetch_threads(driver)
        for thread in threads:
            post = fetch_last_post(driver, thread)
            if post:
                last_post_id = post["id"]
        if last_post_id:
            save_state(last_post_id)
            print("✅ Stare inițială salvată:", last_post_id)
        time.sleep(CHECK_INTERVAL)

    while True:
        try:
            threads = fetch_threads(driver)
            new_posts = []
            for thread in threads:
                post = fetch_last_post(driver, thread)
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

    driver.quit()

if __name__ == "__main__":
    main()
