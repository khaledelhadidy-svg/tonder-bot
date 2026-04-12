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
        return
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(msg_url, json=payload, timeout=10)
    except:
        pass

def check_availability():
    print("Starting Stealth Scan...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # This is the "Human" disguise
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Hide Selenium footprints
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        driver.get(URL)
        # Give it a long time to breathe and bypass any "Checking your browser" screens
        time.sleep(15)

        # Check for the dates
        date_blocks = driver.find_elements(By.CLASS_NAME, "date")
        
        available_dates = []
        phrase_count = 0
        no_slots_phrase = "No more available time slots"

        if not date_blocks:
            # If we find nothing, the bot might be blocked. Let's check the text.
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if "Cloudflare" in page_text or "Access Denied" in page_text:
                print("⛔ BLOCK DETECTED: The website is blocking the GitHub server.")
            else:
                print("Page loaded but no dates found. Might be a blank session.")
        else:
            for block in date_blocks:
                txt = block.text
                if no_slots_phrase in txt:
                    phrase_count += 1
                elif "May" in txt or "June" in txt: # Safety check for months
                    available_dates.append(txt.split('\n')[0])

        print(f"Result: {len(available_dates)} slots, {phrase_count} full.")

        if len(available_dates) > 0:
            send_telegram_msg(f"🚨 <b>DATE FOUND!</b>\n{available_dates[0]}\n<a href='{URL}'>Book!</a>")

    except Exception as e:
        print(f"Error during scan: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
