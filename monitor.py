import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

HOME_URL = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en&uiculture=en"
BOOKING_LINK = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en&uiculture=en"
STATE_FILE = "slot_count_state.txt"

def send_telegram_msg(text):
    """Send notification via Telegram"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing")
        return False
    
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(msg_url, json={
            "chat_id": CHAT_ID, 
            "text": text, 
            "parse_mode": "HTML"
        }, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram notification sent")
            return True
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")
    return False

def setup_driver():
    """Setup Chrome driver with stealth for GitHub Actions"""
    chrome_options = Options()
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    from selenium.webdriver.chrome.service import Service
    service = Service(executable_path='/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        '''
    })
    
    print("✅ Browser ready")
    return driver

def click_button_and_get_calendar(driver):
    """Navigate from home page to calendar by clicking the button"""
    
    print("  Loading home page...")
    driver.get(HOME_URL)
    time.sleep(3)
    
    buttons = driver.find_elements(By.CSS_SELECTOR, ".button")
    print(f"  Found {len(buttons)} buttons")
    
    if len(buttons) == 0:
        buttons = driver.find_elements(By.CSS_SELECTOR, "a.button")
        print(f"  Found {len(buttons)} buttons with alternative selector")
    
    if len(buttons) == 0:
        with open("debug_home.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise Exception("No buttons found on home page")
    
    print(f"  Clicking button: {buttons[0].text.strip()}")
    buttons[0].click()
    time.sleep(5)
    
    current_url = driver.current_url
    print(f"  Navigated to: {current_url}")
    
    if "TimeSelection" not in current_url:
        raise Exception(f"Failed to reach calendar page")
    
    return driver

def count_slots_from_page(driver):
    """Count fully booked slots and find available ones"""
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "date"))
        )
    except:
        pass
    
    date_blocks = driver.find_elements(By.CSS_SELECTOR, ".date.one-queue")
    
    if len(date_blocks) == 0:
        date_blocks = driver.find_elements(By.CLASS_NAME, "date")
    
    print(f"  Found {len(date_blocks)} date blocks")
    
    if len(date_blocks) == 0:
        return 0, []
    
    fully_booked = 0
    available_dates = []
    
    for block in date_blocks:
        try:
            date_elem = block.find_element(By.CLASS_NAME, "header-text")
            date_text = date_elem.text.strip()
            
            warning = block.find_elements(By.XPATH, ".//span[text()='No more available time slots']")
            
            if warning:
                fully_booked += 1
                print(f"    ❌ {date_text} - Fully booked")
            else:
                available_dates.append(date_text)
                print(f"    ✅ {date_text} - AVAILABLE!")
        except Exception as e:
            print(f"    ⚠️ Error parsing block: {e}")
            continue
    
    return fully_booked, available_dates

def load_previous_count():
    """Load the previously stored slot count"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
                return None
    return None

def save_current_count(count):
    """Save the current slot count"""
    with open(STATE_FILE, 'w') as f:
        f.write(str(count))

def check_availability():
    print(f"\n{'='*60}")
    print(f"🔍 Wedding Slot Monitor - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    driver = None
    
    try:
        driver = setup_driver()
        
        print("📱 Step 1: Navigating to calendar...")
        driver = click_button_and_get_calendar(driver)
        
        print("📊 Step 2: Analyzing available slots...")
        fully_booked_count, available_dates = count_slots_from_page(driver)
        
        print(f"\n📈 Fully booked: {fully_booked_count}")
        print(f"   Available: {len(available_dates)}")
        
        previous_count = load_previous_count()
        
        if previous_count is not None:
            print(f"   Previous: {previous_count}")
        
        # Case 1: Available slots found - SEND ALERT
        if available_dates:
            print(f"\n🎉 AVAILABLE SLOTS FOUND!")
            msg = f"🚨 <b>WEDDING SLOT AVAILABLE!</b>\n\n"
            msg += f"✅ <b>{len(available_dates)} date(s)</b> just opened up!\n\n"
            msg += f"📅 Available dates:\n"
            for date in available_dates[:5]:
                msg += f"  • {date}\n"
            if len(available_dates) > 5:
                msg += f"  ... and {len(available_dates) - 5} more\n"
            msg += f"\n🔗 <a href='{BOOKING_LINK}'>CLICK HERE TO BOOK NOW</a>"
            send_telegram_msg(msg)
            save_current_count(fully_booked_count)
            return True
        
        # Case 2: Count changed (slot was booked or cancelled) - SEND ALERT
        elif previous_count is not None and fully_booked_count != previous_count:
            print(f"\n🔔 COUNT CHANGED: {previous_count} → {fully_booked_count}")
            
            if fully_booked_count < previous_count:
                msg = f"🔔 <b>SLOT OPENED UP!</b>\n\n"
                msg += f"Available slots increased!\n"
                msg += f"Fully booked: {previous_count} → {fully_booked_count}\n\n"
                msg += f"🔗 <a href='{BOOKING_LINK}'>CLICK HERE TO CHECK AND BOOK</a>"
            else:
                msg = f"📊 <b>SLOT COUNT UPDATED</b>\n\n"
                msg += f"Fully booked slots: {previous_count} → {fully_booked_count}\n\n"
                msg += f"🔗 <a href='{BOOKING_LINK}'>View Calendar</a>"
            
            send_telegram_msg(msg)
            save_current_count(fully_booked_count)
        
        # Case 3: First run - save baseline, NO ALERT
        elif previous_count is None:
            print(f"\n💾 Saving baseline: {fully_booked_count}")
            save_current_count(fully_booked_count)
        
        # Case 4: No changes - SILENT, NO ALERT
        else:
            print(f"\n✅ No changes")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Only send error alert if it's a critical failure
        if "No buttons found" in str(e) or "Failed to reach calendar" in str(e):
            send_telegram_msg(f"⚠️ Monitor error: {str(e)[:100]}")
        return False
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    check_availability()
