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

# The home page from your letter
HOME_URL = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en&uiculture=en"

# The reservation page URL (will be updated dynamically, but keep as fallback)
RESERVATION_URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

STATE_FILE = "slot_count_state.txt"

def send_telegram_msg(text):
    """Send notification via Telegram"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing")
        print("   Please set TELEGRAM_TOKEN and CHAT_ID environment variables")
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
        else:
            print(f"❌ Telegram error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")
        return False

def setup_driver():
    """Setup Chrome driver with stealth for GitHub Actions"""
    chrome_options = Options()
    
    # Critical for GitHub Actions
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Anti-detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Use system Chrome
    from selenium.webdriver.chrome.service import Service
    service = Service(executable_path='/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Stealth JavaScript
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
    
    # Load home page
    print("  Loading home page...")
    driver.get(HOME_URL)
    time.sleep(3)
    
    # Wait for buttons to load
    wait = WebDriverWait(driver, 10)
    
    # Find all buttons
    buttons = driver.find_elements(By.CSS_SELECTOR, ".button")
    print(f"  Found {len(buttons)} buttons")
    
    if len(buttons) == 0:
        # Try alternative selector
        buttons = driver.find_elements(By.CSS_SELECTOR, "a.button")
        print(f"  Found {len(buttons)} buttons with alternative selector")
    
    if len(buttons) == 0:
        # Save page source for debugging
        with open("debug_home.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise Exception("No buttons found on home page")
    
    # Click the first button (either "Ja" or "Nein" - both lead to calendar)
    print(f"  Clicking button: {buttons[0].text.strip()}")
    buttons[0].click()
    
    # Wait for calendar page to load
    time.sleep(5)
    
    # Verify we're on the calendar page
    current_url = driver.current_url
    print(f"  Navigated to: {current_url}")
    
    if "TimeSelection" not in current_url:
        raise Exception(f"Failed to reach calendar page. Current URL: {current_url}")
    
    return driver, current_url

def count_slots_from_page(driver):
    """Count fully booked slots and find available ones"""
    
    # Wait for date blocks to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "date"))
        )
    except:
        pass
    
    # Find all date blocks
    date_blocks = driver.find_elements(By.CSS_SELECTOR, ".date.one-queue")
    
    if len(date_blocks) == 0:
        # Try alternative selector
        date_blocks = driver.find_elements(By.CLASS_NAME, "date")
    
    print(f"  Found {len(date_blocks)} date blocks")
    
    if len(date_blocks) == 0:
        # Save page source for debugging
        with open("debug_calendar.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return 0, []
    
    fully_booked = 0
    available_dates = []
    
    for block in date_blocks:
        try:
            # Get date text
            date_elem = block.find_element(By.CLASS_NAME, "header-text")
            date_text = date_elem.text.strip()
            
            # Check if fully booked
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
    """Main monitoring function"""
    print(f"\n{'='*60}")
    print(f"🔍 Wedding Slot Monitor - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    driver = None
    current_url = RESERVATION_URL  # Default fallback
    
    try:
        driver = setup_driver()
        
        # Navigate and click button to reach calendar
        print("📱 Step 1: Navigating to calendar...")
        driver, current_url = click_button_and_get_calendar(driver)
        
        # Count slots
        print("📊 Step 2: Analyzing available slots...")
        fully_booked_count, available_dates = count_slots_from_page(driver)
        
        # Calculate total slots (fully booked + available)
        total_slots = fully_booked_count + len(available_dates)
        
        print(f"\n📈 Results:")
        print(f"   Total dates: {total_slots}")
        print(f"   Fully booked: {fully_booked_count}")
        print(f"   Available: {len(available_dates)}")
        print(f"   Booking URL: {current_url}")
        
        # ============================================
        # FORCED TEST - Remove or comment out after testing!
        # This sends a test alert to verify Telegram is working
        # ============================================
        print("\n🧪 Running forced Telegram test...")
        test_message = f"""<b>🧪 WEDDING SLOT MONITOR TEST</b>

✅ Monitor is successfully running!
✅ Browser automation working
✅ Slot detection working

📊 Current Status:
• Total dates: {total_slots}
• Fully booked: {fully_booked_count}
• Available slots: {len(available_dates)}

⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}

The monitor will now alert you automatically when:
• Any slot becomes available
• The fully booked count changes

🔗 <a href='{current_url}'>Click here to BOOK YOUR SLOT</a>"""
        
        test_sent = send_telegram_msg(test_message)
        if test_sent:
            print("   ✅ Test alert sent successfully with booking link!")
        else:
            print("   ⚠️ Test alert failed - check your Telegram credentials")
        # ============================================
        # END OF FORCED TEST
        # ============================================
        
        # Load previous state
        previous_count = load_previous_count()
        
        if previous_count is not None:
            print(f"   Previous fully booked count: {previous_count}")
            print(f"   Change: {fully_booked_count - previous_count}")
        
        # Check for available slots
        if available_dates:
            print(f"\n🎉 AVAILABLE SLOTS FOUND!")
            msg = f"🚨 <b>WEDDING SLOT ALERT!</b>\n\n"
            msg += f"✅ <b>{len(available_dates)} date(s) with availability!</b>\n\n"
            msg += f"📅 Available dates:\n"
            for date in available_dates[:5]:
                msg += f"  • {date}\n"
            if len(available_dates) > 5:
                msg += f"  ... and {len(available_dates) - 5} more\n"
            msg += f"\n🔗 <a href='{current_url}'>CLICK HERE TO BOOK NOW</a>\n\n"
            msg += f"⚠️ Act fast - slots get booked quickly!"
            send_telegram_msg(msg)
            save_current_count(fully_booked_count)
            return True
        
        # Check if count decreased (slot became available)
        elif previous_count is not None and fully_booked_count < previous_count:
            print(f"\n🔔 SLOT COUNT DECREASED!")
            msg = f"🔔 <b>POTENTIAL SLOT OPENING!</b>\n\n"
            msg += f"Fully booked slots decreased from {previous_count} to {fully_booked_count}\n\n"
            msg += f"This means {previous_count - fully_booked_count} slot(s) may have become available!\n\n"
            msg += f"🔗 <a href='{current_url}'>CLICK HERE TO CHECK AND BOOK</a>\n\n"
            msg += f"⚠️ Act fast - slots get booked quickly!"
            send_telegram_msg(msg)
            save_current_count(fully_booked_count)
        
        elif previous_count is None:
            print(f"\n💾 First run - saving baseline: {fully_booked_count}")
            save_current_count(fully_booked_count)
            
            # Send baseline notification with booking link
            baseline_msg = f"""<b>📋 Wedding Slot Monitor - Baseline Set</b>

Monitor has started tracking wedding slots.

📊 Baseline Statistics:
• Total dates tracked: {total_slots}
• Currently fully booked: {fully_booked_count}
• Available slots: {len(available_dates)}

The monitor will alert you immediately when any slot becomes available.

🔗 <a href='{current_url}'>Click here to BOOK YOUR SLOT</a>

⏰ Next check: in 10 minutes"""
            send_telegram_msg(baseline_msg)
        
        else:
            print(f"\n✅ No changes detected. All {fully_booked_count} dates still fully booked.")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Send error notification with booking link
        error_msg = f"""<b>⚠️ Wedding Slot Monitor Error</b>

An error occurred during monitoring:

<code>{str(e)[:200]}</code>

🔗 <a href='{RESERVATION_URL}'>Try booking manually here</a>"""
        send_telegram_msg(error_msg)
        
        if driver:
            try:
                driver.save_screenshot("debug_error.png")
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("📸 Debug files saved")
            except:
                pass
        return False
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    check_availability()
