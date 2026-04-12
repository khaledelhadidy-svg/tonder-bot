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
    print("Starting targeted Tønder scan...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        
        # 1. Wait for the main form to load (based on your source code)
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.ID, "mainForm")))
        
        # Wait a few extra seconds for the JS to populate the date-list section
        time.sleep(5)

        # 2. ANALYSIS OF TEXT (For Fully Booked Labels)
        # We look for the "warning-message" class found in your HTML
        full_page_text = driver.find_element(By.TAG_NAME, "body").text
        no_slots_phrase = "No more available time slots"
        phrase_count = full_page_text.count(no_slots_phrase)

        # 3. ANALYSIS OF SLOTS (Looking for things that AREN'T "No more available")
        # Available slots in this system usually appear as buttons or links inside the "date" divs
        # We look for any element that might trigger the 'selectTime' function
        elements = driver.find_elements(By.CSS_SELECTOR, ".date.one-queue")
        
        available_dates = []
        for date_div in elements:
            content = date_div.text
            if no_slots_phrase not in content:
                # If the 'No more' phrase is NOT in this date block, it might have a slot!
                date_header = date_div.find_element(By.CLASS_NAME, "header-text").text
                available_dates.append(date_header)

        print(f"Scan complete. Found {len(available_dates)} available dates and {phrase_count} 'Full' labels.")

        # 4. LOGIC FOR ALERTING
        if len(available_dates) > 0:
            msg = f"🚨 <b>WEDDING SLOT FOUND!</b>\nDates with availability:\n" + "\n".join(available_dates) + f"\n\n🔗 <a href='{URL}'>Book Now</a>"
            send_telegram_msg(msg)
            print("Alert sent: Available dates found!")

        elif phrase_count > 0:
            print(f"System Check: I can see {phrase_count} fully booked dates. Script is working, but no dates are open.")

        else:
            print("Warning: The page loaded but no dates or labels were found. Check the URL/Session.")

    except Exception as e:
        print(f"Check failed: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
