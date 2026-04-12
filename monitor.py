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
# We start at the HOME page of the marriage (vielse) section to get a session
HOME_URL = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en"
# This is where we want to end up
TARGET_URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(msg_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass

def check_availability():
    print("Starting Human-Flow Scan...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # STEP 1: Get the session cookie from the homepage
        print("Fetching session...")
        driver.get(HOME_URL)
        time.sleep(5) 

        # STEP 2: Now go to the specific calendar page
        print("Navigating to calendar...")
        driver.get(TARGET_URL)
        time.sleep(10) # Wait for JS to render

        # STEP 3: Check for dates
        # Based on your HTML source, we look for the date blocks
        date_blocks = driver.find_elements(By.CLASS_NAME, "date")
        
        available_dates = []
        phrase_count = 0
        no_slots_phrase = "No more available time slots"

        for block in date_blocks:
            txt = block.text
            if no_slots_phrase in txt:
                phrase_count += 1
            elif "2026" in txt: # If the year is there but the 'No slots' phrase isn't...
                available_dates.append(txt.split('\n')[0])

        print(f"Final Count: {len(available_dates)} available, {phrase_count} full.")

        if len(available_dates) > 0:
            msg = f"🚨 <b>DATE ALERT!</b>\nAvailable: {available_dates[0]}\n\n<a href='{TARGET_URL}'>BOOK NOW</a>"
            send_telegram_msg(msg)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
