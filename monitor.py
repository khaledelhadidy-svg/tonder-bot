import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Try to import stealth, but fallback gracefully if not available
try:
    from selenium_stealth import stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("⚠️ selenium-stealth not available, using basic stealth")

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Direct URL to the TimeSelection page (from your working link)
TARGET_URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing")
        return
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(msg_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if response.status_code != 200:
            print(f"❌ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def setup_driver():
    """Setup Chrome driver with anti-detection measures"""
    chrome_options = Options()
    
    # Headless mode for GitHub Actions
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Anti-detection arguments
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Try to use system Chrome first (GitHub Actions), fallback to webdriver-manager
    try:
        from selenium.webdriver.chrome.service import Service
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Using system Chrome driver")
    except Exception as e:
        print(f"⚠️ System Chrome failed ({e}), using webdriver-manager")
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Apply stealth if available
    if STEALTH_AVAILABLE:
        try:
            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                run_on_insecure_origins=True,
            )
            print("✅ Stealth mode enabled")
        except Exception as e:
            print(f"⚠️ Stealth injection failed: {e}")
    else:
        # Manual stealth
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        print("✅ Basic stealth applied")
    
    return driver

def check_availability():
    print("🚀 Starting Wedding Slot Monitor...")
    driver = None
    
    try:
        driver = setup_driver()
        
        # Navigate directly to the TimeSelection page
        print(f"📱 Loading page: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # Wait for the date blocks to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "date")))
        
        # Extra wait for dynamic content
        time.sleep(3)
        
        # Find all date blocks
        date_blocks = driver.find_elements(By.CSS_SELECTOR, ".date.one-queue")
        print(f"📅 Found {len(date_blocks)} date blocks")
        
        if not date_blocks:
            print("❌ No date blocks found!")
            # Save page source for debugging
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("📄 Saved debug_page.html")
            return False
        
        available_dates = []
        fully_booked_dates = []
        
        for block in date_blocks:
            try:
                # Get the date text from header-text span
                date_element = block.find_element(By.CSS_SELECTOR, ".header-text")
                date_text = date_element.text.strip()
                
                # Check if this date has availability
                # Look for the warning message that indicates no slots
                warning_elements = block.find_elements(By.CSS_SELECTOR, ".warning-message")
                
                if warning_elements:
                    # This date has "No more available time slots"
                    fully_booked_dates.append(date_text)
                    print(f"❌ FULL: {date_text}")
                else:
                    # No warning message means slots are available!
                    available_dates.append(date_text)
                    print(f"✅ AVAILABLE: {date_text}")
                    
                    # Try to find time slots for extra info
                    try:
                        time_slots = block.find_elements(By.CSS_SELECTOR, ".time-slot, [onclick*='selectTime']")
                        if time_slots:
                            print(f"   → {len(time_slots)} time slots available")
                    except:
                        pass
                        
            except Exception as e:
                print(f"⚠️ Error parsing block: {e}")
                continue
        
        print(f"\n📊 SUMMARY: {len(available_dates)} available, {len(fully_booked_dates)} fully booked")
        
        # Send alert if any date is available
        if available_dates:
            msg = f"🚨 <b>WEDDING SLOT ALERT!</b>\n\n"
            msg += f"📅 Available dates found:\n"
            for date in available_dates[:5]:  # Show first 5
                msg += f"  ✅ {date}\n"
            
            if len(available_dates) > 5:
                msg += f"  ... and {len(available_dates) - 5} more\n"
            
            msg += f"\n🔗 <a href='{TARGET_URL}'>Book Now</a>"
            send_telegram_msg(msg)
            print("✅ Alert sent to Telegram!")
            
            # Save screenshot of available slots
            screenshot_path = f"available_slots_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"📸 Screenshot saved: {screenshot_path}")
            return True
        else:
            print("❌ No available slots found - all dates are fully booked")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        if driver:
            try:
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("📄 Debug HTML saved to debug_page.html")
                driver.save_screenshot("debug_error.png")
                print("📸 Error screenshot saved to debug_error.png")
            except:
                pass
        return False
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    check_availability()
