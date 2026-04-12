import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(msg_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_availability():
    print("Starting targeted Tønder scan (No-Iframe Version)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        
        # 1. WAIT FOR THE MAIN FORM (Based on your source code id="mainForm")
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.ID, "mainForm")))
        
        # Small sleep to let the JavaScript finish rendering the list
        time.sleep(5)

        # 2. ANALYSIS
        # Get all date containers
        date_blocks = driver.find_elements(By.CLASS_NAME, "date.one-queue")
        
        available_dates = []
        no_slots_phrase = "No more available time slots"
        phrase_count = 0

        for block in date_blocks:
            block_text = block.text
            if no_slots_phrase in block_text:
                phrase_count += 1
            else:
                # If the 'Full' phrase is missing, this date has a slot!
                # Extract the date text (e.g., "Tuesday May 5, 2026")
                try:
                    date_name = block.find_element(By.CLASS_NAME, "header-text").text
                    if date_name:
                        available_dates.append(date_name)
                except:
                    available_dates.append("Unknown Date Slot Found")

        print(f"Scan complete. Found {len(available_dates)} available dates and {phrase_count} 'Full' labels.")

        # 3. LOGIC FOR ALERTING
        if len(available_dates) > 0:
            msg = f"🚨 <b>WEDDING SLOT FOUND!</b>\n\nAvailable:\n" + "\n".join(available_dates) + f"\n\n🔗 <a href='{URL}'>Book Now</a>"
            send_telegram_msg(msg)
            print("Alert sent: Clickable slots found.")

        elif phrase_count > 0:
            print(f"Confirmed: Site is visible. {phrase_count} dates are fully booked. Keep waiting!")

        else:
            print("Warning: No date blocks or 'Full' labels found. The site might have blocked the bot.")

    except Exception as e:
        print(f"Check failed: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
