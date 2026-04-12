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
    print("Starting safety-first scan...")
    
    chrome_options = Options()
    # "headless=new" is the modern standard for Selenium 4+
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Adding a User-Agent helps avoid being blocked as a bot
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL)
        
        # 1. WAIT FOR IFRAME AND SWITCH
        # FrontDesk Suite loads the calendar inside an iframe.
        wait = WebDriverWait(driver, 30)
        try:
            # Wait for any iframe to appear and switch to it
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
            print("Successfully switched to the reservation iframe.")
        except Exception as e:
            print("No iframe found or timeout. Continuing on main page...")

        # 2. WAIT FOR CONTENT TO LOAD INSIDE THE FRAME
        # We look for the phrase you provided in the page content
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Additional buffer for JS to finish rendering dates
        time.sleep(5) 

        # 3. ANALYSIS
        full_page_text = driver.find_element(By.TAG_NAME, "body").text
        no_slots_phrase = "No more available time slots"
        phrase_count = full_page_text.count(no_slots_phrase)

        # Look for the 'Select' buttons which only appear when a slot is open
        # We search for text specifically to catch slots
        clickable_elements = []
        # Finding elements that contain "Select" (common in FrontDesk Suite)
        potential_slots = driver.find_elements(By.XPATH, "//*[contains(text(), 'Select') or contains(text(), '10:') or contains(text(), '11:')]")
        
        for item in potential_slots:
            if item.is_displayed() and item.text.strip():
                clickable_elements.append(item.text.strip())

        print(f"Scan complete. Found {len(clickable_elements)} booking elements and {phrase_count} 'Full' labels.")

        # 4. LOGIC FOR ALERTING
        if len(clickable_elements) > 0:
            msg = f"🚨 <b>SLOT ALERT!</b> Found {len(clickable_elements)} potential slots!\n<b>Details:</b> {', '.join(clickable_elements[:5])}\n\n🔗 <a href='{URL}'>Book Now</a>"
            send_telegram_msg(msg)
            print("Alert sent: Clickable slots found.")

        elif phrase_count > 0:
            print(f"Confirmed: Site is visible. {phrase_count} dates are fully booked.")

        elif "Tuesday" not in full_page_text and "Thursday" not in full_page_text:
            # This triggers if we switched frames but the page is still blank
            print("Warning: Calendar days not found. Scraper might be blocked or page layout changed.")
        
        else:
            print("No slots found, but the page loaded correctly.")

    except Exception as e:
        print(f"Check failed: {e}")
        # Only send error to Telegram if it's a critical failure
        # send_telegram_msg(f"❌ Bot Error: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
