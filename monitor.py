import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials missing.")
        return
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.get(msg_url, params=params)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_availability():
    print("Starting safety-first scan...")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        # Give the JavaScript list 20 seconds to fully load all months
        time.sleep(20) 

        # 1. Search for any clickable 'Select' buttons or time links
        # This is the most reliable way to find a cancellation.
        links = driver.find_elements(By.TAG_NAME, "a")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        
        clickable_elements = []
        for item in (links + buttons):
            # We look for common booking keywords in buttons
            text = item.text.lower()
            if any(word in text for word in ["select", "choose", "reserve", "book", "vail", "10:", "11:", "12:", "13:", "09:"]):
                clickable_elements.append(item.text)

        # 2. Analyze the text content for "Full" messages
        full_page_text = driver.find_element(By.TAG_NAME, "body").text
        no_slots_phrase = "No more available time slots"
        phrase_count = full_page_text.count(no_slots_phrase)

        print(f"Scan complete. Found {len(clickable_elements)} booking elements and {phrase_count} 'Full' labels.")

        # LOGIC FOR ALERTING:
        # If we find a booking button OR if the text seems to have changed significantly
        if len(clickable_elements) > 0:
            msg = f"🚨 SLOT ALERT! Found {len(clickable_elements)} clickable time slots!\nDates: {', '.join(clickable_elements[:5])}...\nLink: {URL}"
            send_telegram_msg(msg)
            print("Alert sent: Clickable slots found.")

        elif phrase_count == 0 and "Tuesday" in full_page_text:
            # If the dates are there but the 'No more available' text is totally gone
            msg = f"⚠️ WARNING: The 'No more available' labels have disappeared. Check immediately!\nLink: {URL}"
            send_telegram_msg(msg)
            print("Alert sent: Labels missing.")

        else:
            print("No changes detected. Everything is still fully booked.")

    except Exception as e:
        print(f"Check failed: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
