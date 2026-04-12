import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Direct URL to the TimeSelection page
TARGET_URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

# File to store the previous count
STATE_FILE = "slot_count_state.txt"

def send_telegram_msg(text):
    """Send notification via Telegram"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing")
        return
    
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(msg_url, json={
            "chat_id": CHAT_ID, 
            "text": text, 
            "parse_mode": "HTML"
        }, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram notification sent")
        else:
            print(f"❌ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def count_no_slots_with_selenium(driver):
    """
    Count occurrences of "No more available time slots" using Selenium
    """
    # Wait for the date blocks to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "date"))
        )
    except:
        pass  # Continue anyway, we'll check manually
    
    # Method 1: Find all warning spans by text
    warning_spans = driver.find_elements(By.XPATH, "//span[text()='No more available time slots']")
    count_spans = len(warning_spans)
    
    # Method 2: Find all warning divs
    warning_divs = driver.find_elements(By.CLASS_NAME, "warning-message")
    count_divs = len(warning_divs)
    
    # Method 3: Count date blocks that have the warning
    date_blocks = driver.find_elements(By.CLASS_NAME, "date.one-queue")
    
    # Find available dates (blocks without warning)
    available_dates = []
    for block in date_blocks:
        try:
            # Check if this block has the warning message
            warning = block.find_elements(By.XPATH, ".//span[text()='No more available time slots']")
            if not warning:
                # No warning means slots are available!
                try:
                    date_text = block.find_element(By.CLASS_NAME, "header-text").text
                    available_dates.append(date_text)
                except:
                    pass
        except:
            continue
    
    print(f"  Found {count_spans} warning spans")
    print(f"  Found {count_divs} warning divs")
    print(f"  Found {len(date_blocks)} total date blocks")
    print(f"  Available dates: {len(available_dates)}")
    
    # Use the most reliable count (spans seem most consistent)
    return max(count_spans, count_divs), available_dates

def setup_stealth_driver():
    """Setup Chrome driver with maximum stealth"""
    chrome_options = Options()
    
    # Essential headless options for GitHub Actions
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Anti-detection measures
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Additional stealth
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    
    # Try to use system Chrome first
    try:
        from selenium.webdriver.chrome.service import Service
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Using system Chrome driver")
    except Exception as e:
        print(f"⚠️ System Chrome failed ({e}), using webdriver-manager")
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Execute stealth JavaScript
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        '''
    })
    
    print("✅ Stealth mode applied")
    return driver

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
    try:
        # Setup driver
        print("🚀 Initializing browser...")
        driver = setup_stealth_driver()
        
        # Navigate directly to the page
        print(f"📱 Loading page...")
        driver.get(TARGET_URL)
        
        # Wait for page to load
        time.sleep(5)
        
        # Count the warning messages
        print("📊 Analyzing page content...")
        no_slots_count, available_dates = count_no_slots_with_selenium(driver)
        
        # Load previous state
        previous_count = load_previous_count()
        
        print(f"\n📈 Current 'No slots' count: {no_slots_count}")
        if previous_count is not None:
            print(f"📉 Previous count: {previous_count}")
            print(f"📊 Change: {no_slots_count - previous_count}")
        
        # Check for available slots
        if available_dates:
            print(f"\n🎉 AVAILABLE SLOTS DETECTED!")
            print(f"📅 Available dates: {', '.join(available_dates)}")
            
            # Send Telegram alert
            msg = f"🚨 <b>WEDDING SLOT ALERT!</b>\n\n"
            msg += f"✅ <b>{len(available_dates)} date(s) with availability!</b>\n\n"
            msg += f"📅 Available:\n"
            for date in available_dates[:5]:
                msg += f"  • {date}\n"
            msg += f"\n🔗 <a href='{TARGET_URL}'>Book Now</a>"
            
            send_telegram_msg(msg)
            
            # Save current state
            save_current_count(no_slots_count)
            return True
        
        # Check if count has changed
        elif previous_count is not None and no_slots_count != previous_count:
            print(f"\n⚠️ SLOT COUNT CHANGED!")
            print(f"   Was: {previous_count}, Now: {no_slots_count}")
            
            # If count decreased, a slot might have opened
            if no_slots_count < previous_count:
                msg = f"🔔 <b>POTENTIAL SLOT OPENING!</b>\n\n"
                msg += f"Available slot count changed from {previous_count} to {no_slots_count}\n\n"
                msg += f"This might mean a slot has become available!\n\n"
                msg += f"🔗 <a href='{TARGET_URL}'>Check Now</a>"
                send_telegram_msg(msg)
            
            save_current_count(no_slots_count)
        
        elif no_slots_count == 0 and previous_count is None:
            # First run - save the count
            print(f"\n💾 First run - saving baseline count: {no_slots_count}")
            save_current_count(no_slots_count)
        
        else:
            print(f"\n✅ No changes detected. All {no_slots_count} dates still fully booked.")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Save screenshot for debugging
        if driver:
            try:
                driver.save_screenshot("debug_error.png")
                print("📸 Error screenshot saved to debug_error.png")
                
                # Save page source
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("📄 Debug HTML saved to debug_page.html")
            except:
                pass
        
        return False
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    check_availability()
