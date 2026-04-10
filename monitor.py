import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
# These are pulled from your GitHub Repo Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

def send_telegram_msg(text):
    """Sends a notification to Telegram. Raises an error if it fails."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise ValueError(f"MISSING CREDENTIALS! Token found: {bool(TELEGRAM_TOKEN)}, ID found: {bool(CHAT_ID)}")
    
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    
    try:
        response = requests.get(msg_url, params=params)
        if response.status_code != 200:
            print(f"Telegram API Error: {response.text}")
        else:
            print("Telegram message sent successfully!")
    except Exception as e:
        print(f"Failed to connect to Telegram: {e}")

def check_availability():
    """Initializes the browser and checks the Tønder calendar."""
    print("Initializing browser...")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"Navigating to: {URL}")
        driver.get(URL)
        
        # We wait 15 seconds because the FrontDesk calendar is slow to load via JavaScript
        time.sleep(15) 

        # Look for day elements that are NOT disabled and NOT empty
        days = driver.find_elements(By.CSS_SELECTOR, ".day:not(.disabled):not(.empty)")

        if len(days) > 0:
            found_dates = [day.text.strip() for day in days if day.text.strip()]
            
            if found_dates:
                message = f"🔔 SLOT FOUND! Dates available: {', '.join(found_dates)}\nLink: {URL}"
                print(message)
                send_telegram_msg(message)
            else:
                # If we found elements but no text, it might still be loading or they are blocked
                print("Detected potential slots, but no text was visible in the elements.")
                # Optional: send a 'Maybe' notification
                # send_telegram_msg("The bot detected a change in the calendar! Check manually: " + URL)
        else:
            print("Checked: No available slots found at this time.")

    except Exception as e:
        print(f"An error occurred during the web check: {e}")
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    # --- HARD TEST ---
    # This ensures your Telegram setup works every time the script starts.
    # Once you receive a message and are confident, you can delete the line below.
    send_telegram_msg("🤖 Bot is starting a new check...")

    check_availability()
