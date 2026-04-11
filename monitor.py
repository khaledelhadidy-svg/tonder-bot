import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
# These are pulled from your GitHub Secrets
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
        # Using POST is more reliable for Telegram
        requests.post(msg_url, json=payload, timeout=10)
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
        links = driver.find_elements(By.TAG_NAME, "a")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        
        clickable_elements = []
        for item in (links + buttons):
            text = item.text.lower()
            # Look for booking keywords or time patterns (e.g., 10:30)
            if any(word in text for word in ["select", "choose", "reserve", "book", "vail", "10:", "11:", "12:", "13:", "09:"]):
                if item.text.strip(): # Avoid empty strings
                    clickable_elements.append(item.text.strip())

        # 2. Analyze the text content for "Full" messages
        full_page_text = driver.find_element(By.TAG_NAME, "body").text
        no_slots_phrase = "No more available time slots"
        phrase_count = full_page_text.count(no_slots_phrase)

        print(f"Scan complete. Found {len(clickable_elements)} booking elements and {phrase_count} 'Full' labels.")

        # LOGIC FOR ALERTING:
        if len(clickable_elements) > 0:
            msg = f"🚨 <b>SLOT ALERT!</b> Found {len(clickable_elements)} clickable time slots!\n<b>Details:</b> {', '.join(clickable_elements[:5])}\n\n🔗 <a href='{URL}'>Book Now</a>"
            send_telegram_msg(msg)
            print("Alert sent: Clickable slots found.")

        elif phrase_count == 0 and "Tuesday" in full_page_text:
            msg = f"⚠️ <b>WARNING:</b> The 'No more available' labels have disappeared. Check immediately!\n\n🔗 <a href='{URL}'>Link Here</a>"
            send_telegram_msg(msg)
            print("Alert sent: Labels missing.")

        else:
            print("No changes detected. Everything is still fully booked.")

    except Exception as e:
        print(f"Check failed: {e}")
        # This line below was likely the one with the extra space
        send_telegram_msg(f"❌ Bot Error: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # If you want to keep the "I am alive" message, keep the next 2 lines. 
    # Otherwise, delete them to go silent.
    current_time = time.strftime("%H:%M:%S")
    send_telegram_msg(f"🤖 Bot Status: Active and checking Tønder at {current_time}. (No slots found yet)")
    
    check_availability()
