import os
import time
import requests
import json
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
STATE_FILE = "slot_state.json"

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(msg_url, json={
            "chat_id": CHAT_ID, 
            "text": text, 
            "parse_mode": "HTML"
        }, timeout=10)
        return response.status_code == 200
    except:
        return False

def setup_driver():
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
    
    return driver

def click_button_and_get_calendar(driver):
    print("  Loading home page...")
    driver.get(HOME_URL)
    time.sleep(3)
    
    buttons = driver.find_elements(By.CSS_SELECTOR, ".button")
    if len(buttons) == 0:
        buttons = driver.find_elements(By.CSS_SELECTOR, "a.button")
    
    if len(buttons) == 0:
        raise Exception("No buttons found on home page")
    
    print(f"  Clicking button: {buttons[0].text.strip()}")
    buttons[0].click()
    time.sleep(5)
    
    if "TimeSelection" not in driver.current_url:
        raise Exception("Failed to reach calendar page")
    
    return driver

def get_slots_from_page(driver):
    """Get all dates and their availability status"""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "date"))
        )
    except:
        pass
    
    date_blocks = driver.find_elements(By.CSS_SELECTOR, ".date.one-queue")
    if len(date_blocks) == 0:
        date_blocks = driver.find_elements(By.CLASS_NAME, "date")
    
    slots = {}
    for block in date_blocks:
        try:
            date_elem = block.find_element(By.CLASS_NAME, "header-text")
            date_text = date_elem.text.strip()
            
            warning = block.find_elements(By.XPATH, ".//span[text()='No more available time slots']")
            is_available = len(warning) == 0
            
            slots[date_text] = is_available
            status = "✅ AVAILABLE" if is_available else "❌ Fully booked"
            print(f"    {status}: {date_text}")
        except:
            continue
    
    return slots

def load_previous_state():
    """Load previously stored slots data from file"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return None
    return None

def save_current_state(slots):
    """Save current slots data to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(slots, f, indent=2)

def check_availability():
    print(f"\n{'='*60}")
    print(f"🔍 Wedding Slot Monitor TEST - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    driver = None
    
    try:
        driver = setup_driver()
        print("📱 Navigating to calendar...")
        driver = click_button_and_get_calendar(driver)
        
        print("📊 Analyzing slots...")
        current_slots = get_slots_from_page(driver)
        
        total_dates = len(current_slots)
        available_dates = [date for date, available in current_slots.items() if available]
        fully_booked_count = total_dates - len(available_dates)
        
        print(f"\n📈 Results:")
        print(f"   Total dates: {total_dates}")
        print(f"   Fully booked: {fully_booked_count}")
        print(f"   Available: {len(available_dates)}")
        
        if available_dates:
            print(f"   🎉 AVAILABLE: {', '.join(available_dates)}")
        
        previous_state = load_previous_state()
        
        # ============================================
        # FORCED TEST SECTION - Remove after verifying
        # ============================================
        print(f"\n🧪 FORCED TEST MODE ACTIVE 🧪")
        print(f"   State file exists: {os.path.exists(STATE_FILE)}")
        
        if previous_state:
            print(f"   Previous state has {len(previous_state)} dates")
            print(f"   First 3 dates from previous state:")
            for i, date in enumerate(list(previous_state.keys())[:3]):
                print(f"      {i+1}. {date}: {'Available' if previous_state[date] else 'Booked'}")
        else:
            print(f"   No previous state found - this is FIRST RUN")
        
        print(f"\n   Current state has {len(current_slots)} dates")
        print(f"   First 3 dates from current state:")
        for i, date in enumerate(list(current_slots.keys())[:3]):
            print(f"      {i+1}. {date}: {'Available' if current_slots[date] else 'Booked'}")
        # ============================================
        # END FORCED TEST SECTION
        # ============================================
        
        # First run - save state and send notification
        if previous_state is None:
            print(f"\n💾 FIRST RUN - saving baseline")
            save_current_state(current_slots)
            
            # Send startup notification
            test_msg = f"""<b>🧪 TEST: First Run - Baseline Saved</b>

✅ Monitor started successfully
✅ State file created with {total_dates} dates

📊 Current Status:
• Total dates: {total_dates}
• Fully booked: {fully_booked_count}
• Available slots: {len(available_dates)}

🔗 <a href='{BOOKING_LINK}'>Booking Link</a>

⚠️ THIS IS A TEST - Next run should NOT send this message"""
            
            send_telegram_msg(test_msg)
            return True
        
        # Compare with previous state
        previous_available = [date for date, available in previous_state.items() if available]
        
        # Find NEWLY available slots (WERE booked, NOW available)
        newly_available = []
        for date in current_slots:
            if current_slots[date]:  # Currently available
                if date in previous_state and not previous_state[date]:  # Was booked
                    newly_available.append(date)
                elif date not in previous_state:  # Brand new date that is available
                    newly_available.append(date)
        
        # Find NEWLY booked slots (were available, now booked)
        newly_booked = [date for date in current_slots if not current_slots[date] and date in previous_state and previous_state[date]]
        
        # Find BRAND NEW dates (not in previous state) - even if booked
        new_dates = [date for date in current_slots if date not in previous_state]
        
        # Find REMOVED dates (in previous but not current)
        removed_dates = [date for date in previous_state if date not in current_slots]
        
        # ============================================
        # TEST VERIFICATION - Check if state persisted
        # ============================================
        print(f"\n🧪 STATE PERSISTENCE CHECK:")
        print(f"   Previous run had {len(previous_state)} dates")
        print(f"   Current run has {len(current_slots)} dates")
        
        if len(previous_state) > 0 and len(current_slots) > 0:
            # Check if any dates match between runs
            common_dates = set(previous_state.keys()) & set(current_slots.keys())
            if common_dates:
                print(f"   ✅ State persisted! Found {len(common_dates)} common dates")
            else:
                print(f"   ❌ WARNING: No common dates found - state may not be persisting!")
        
        # Send test notification if state persisted correctly (ONCE)
        if not newly_available and not newly_booked and not new_dates and not removed_dates:
            # No changes detected - send confirmation that state is working
            print(f"\n✅ No changes detected - State persistence is WORKING!")
            
            test_msg = f"""<b>🧪 TEST: State Persistence Working!</b>

✅ Monitor ran again and found NO changes
✅ Previous state was loaded successfully
✅ You will ONLY receive alerts when slots change

📊 Current Status:
• Total dates: {total_dates}
• Fully booked: {fully_booked_count}
• Available slots: {len(available_dates)}

🔗 <a href='{BOOKING_LINK}'>Booking Link</a>

⚠️ THIS IS THE LAST TEST MESSAGE
Next run will be SILENT unless slots change"""
            
            send_telegram_msg(test_msg)
            save_current_state(current_slots)
            return True
        
        # If changes detected, send alert
        elif newly_available or newly_booked or new_dates or removed_dates:
            print(f"\n🔔 CHANGES DETECTED!")
            
            msg = f"<b>📅 WEDDING SLOT UPDATE</b>\n\n"
            
            if newly_available:
                msg += f"🎉 <b>SLOT(S) JUST OPENED UP!</b>\n"
                for date in newly_available:
                    msg += f"   ✅ {date}\n"
                msg += f"\n"
            
            if newly_booked:
                msg += f"❌ <b>Slot(s) just got booked:</b>\n"
                for date in newly_booked[:3]:
                    msg += f"   • {date}\n"
                msg += f"\n"
            
            if new_dates:
                msg += f"➕ <b>New date(s) added:</b>\n"
                for date in new_dates[:3]:
                    msg += f"   • {date}\n"
                msg += f"\n"
            
            if removed_dates:
                msg += f"➖ <b>Date(s) removed:</b>\n"
                for date in removed_dates[:3]:
                    msg += f"   • {date}\n"
                msg += f"\n"
            
            msg += f"📊 <b>Current status:</b>\n"
            msg += f"   Fully booked: {fully_booked_count}\n"
            msg += f"   Available: {len(available_dates)}\n"
            
            if available_dates:
                msg += f"\n📅 <b>All available dates:</b>\n"
                for date in available_dates[:5]:
                    msg += f"   • {date}\n"
            
            msg += f"\n🔗 <a href='{BOOKING_LINK}'>CLICK HERE TO BOOK</a>"
            
            send_telegram_msg(msg)
            save_current_state(current_slots)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        send_telegram_msg(f"⚠️ Monitor error: {str(e)[:100]}")
        return False
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    check_availability()
