import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "8506189872:AAHK-x8ICGdaZW_if1yDXVNwrJGM8lUtqY4"
CHAT_ID = "8662424755"
URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"
CHECK_INTERVAL = 300  # Seconds between checks (300s = 5 minutes)

def send_telegram_msg(text):
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    requests.get(msg_url, params=params)

def check_availability():
    # Setup Chrome options (Headless means no window pops up)
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        time.sleep(5)  # Wait for the calendar to load

        # Find all calendar day elements
        # Note: FrontDeskSuite usually marks available days with a specific class or lack of 'disabled'
        days = driver.find_elements(By.CSS_SELECTOR, ".day:not(.disabled):not(.empty)")

        if len(days) > 0:
            found_dates = [day.text for day in days if day.text.strip()]
            message = f"🔔 SLOT FOUND! The following dates seem available: {', '.join(found_dates)}\nLink: {URL}"
            print(message)
            send_telegram_msg(message)
        else:
            print("Checked: No slots available right now.")

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print("Bot started... Press Ctrl+C to stop.")
    while True:
        check_availability()
        time.sleep(CHECK_INTERVAL)