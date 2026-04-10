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
        # This will now raise an error so we can see it in the logs
        raise ValueError(f"MISSING CREDENTIALS! Token: {bool(TELEGRAM_TOKEN)}, ID: {bool(CHAT_ID)}")
    
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    
    response = requests.get(msg_url, params=params)
    if response.status_code != 200:
        raise Exception(f"Telegram API Error: {response.text}")
    else:
        print("Telegram message sent successfully!")

def check_availability():
    print("Checking for available slots...")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        time.sleep(7)  # Increased wait time for slow loading

        # Look for days that are NOT disabled and NOT empty
        days = driver.find_elements(By.CSS_SELECTOR, ".day:not(.disabled):not(.empty)")

        if True:  # Temporary test
            found_dates = [day.text.strip() for day in days if day.text.strip()]
            if found_dates:
                message = f"🔔 SLOT FOUND! Dates available: {', '.join(found_dates)}\nLink: {URL}"
                print(message)
                send_telegram_msg(message)
            else:
                print("No text found in available day elements.")
        else:
            print("Checked: No slots available right now.")

    except Exception as e:
        print(f"Error occurred during check: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # On GitHub Actions, we run once. The 'cron' schedule handles the repetition.
    check_availability()
