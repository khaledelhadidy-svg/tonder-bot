import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

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
HOME_URL = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en"

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
    chrome_options.add_argument("--start-maximized")
    
    # Additional anti-detection arguments
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Disable automation flags
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    
    # Try to use system Chrome first (GitHub Actions), fallback to webdriver-manager
    try:
        # For GitHub Actions with chromium-browser installed
        from selenium.webdriver.chrome.service import Service
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Using system Chrome driver")
    except Exception as e:
        print(f"⚠️ System Chrome failed ({e}), using webdriver-manager")
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
    print("🚀 Starting Enhanced Session-Persistent Scan...")
    driver = None
    
    try:
        driver = setup_driver()
        
        # Step 1: Navigate to Home page
        print("📱 Step 1: Establishing session from Home page...")
        driver.get(HOME_URL)
        time.sleep(3)
        
        # Step 2: Wait for page to load
        wait = WebDriverWait(driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "mainForm")))
            print("✅ Main form detected")
        except:
            print("⚠️ Main form not found, continuing anyway...")
        
        # Step 3: Find and click the marriage button
        print("🔍 Step 2: Looking for marriage selection button...")
        time.sleep(2)
        
        # Try multiple selector strategies for the button
        button_selectors = [
            "a[href*='TimeSelection']",
            "button[onclick*='TimeSelection']",
            "a:contains('Marriage')",
            "button:contains('Marriage')",
            ".btn-primary",
            "input[value*='Marriage']"
        ]
        
        button_clicked = False
        for selector in button_selectors:
            try:
                # JavaScript click to avoid detection
                button = driver.find_element(By.CSS_SELECTOR, selector)
                driver.execute_script("arguments[0].click();", button)
                print(f"✅ Clicked button with selector: {selector}")
                button_clicked = True
                break
            except:
                continue
        
        if not button_clicked:
            # Try to find by text content
            try:
                elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Marriage') or contains(text(), 'Vielse')]")
                for elem in elements:
                    if elem.is_displayed() and elem.tag_name in ['a', 'button', 'input']:
                        driver.execute_script("arguments[0].click();", elem)
                        print("✅ Clicked button by text content")
                        button_clicked = True
                        break
            except:
                pass
        
        if not button_clicked:
            raise Exception("Could not find marriage button")
        
        # Step 4: Wait for calendar to load
        print("📅 Step 3: Waiting for calendar to load...")
        time.sleep(5)
        
        # Step 5: Extract date information
        print("🔎 Step 4: Scanning for available dates...")
        time.sleep(2)
        
        # Try multiple selectors for date blocks
        date_blocks = []
        for selector in [".date.one-queue", ".date", "[class*='date']"]:
            date_blocks = driver.find_elements(By.CSS_SELECTOR, selector)
            if date_blocks:
                print(f"✅ Found {len(date_blocks)} date blocks with selector: {selector}")
                break
        
        if not date_blocks:
            print("❌ No date blocks found!")
            # Save page source for debugging
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("📄 Saved debug_page.html")
            return False
        
        available_dates = []
        full_dates = []
        no_slots_phrase = "No more available time slots"
        
        for idx, block in enumerate(date_blocks):
            try:
                # Try to get header text
                header_text = ""
                for header_selector in [".header-text", "h3", "h4", ".date-header"]:
                    try:
                        header_elem = block.find_element(By.CSS_SELECTOR, header_selector)
                        header_text = header_elem.text.strip()
                        break
                    except:
                        continue
                
                if not header_text:
                    # Use block text as fallback
                    header_text = block.text.split('\n')[0].strip()
                
                # Check availability
                block_html = block.get_attribute('innerHTML')
                
                if no_slots_phrase not in block_html:
                    available_dates.append(header_text)
                    print(f"✅ AVAILABLE: {header_text}")
                    
                    # Try to count time slots
                    try:
                        time_slots = block.find_elements(By.CSS_SELECTOR, ".time-slot, [onclick*='selectTime']")
                        if time_slots:
                            print(f"   → {len(time_slots)} time slots available")
                    except:
                        pass
                else:
                    full_dates.append(header_text)
                    print(f"❌ FULL: {header_text}")
                    
            except Exception as e:
                print(f"⚠️ Error parsing block {idx}: {e}")
                continue
        
        print(f"\n📊 SUMMARY: {len(available_dates)} available, {len(full_dates)} fully booked")
        
        # Send alert if any date is available
        if available_dates:
            msg = f"🚨 <b>WEDDING SLOT ALERT!</b>\n\n"
            msg += f"📅 Available dates:\n"
            for date in available_dates[:5]:
                msg += f"  • {date}\n"
            
            # Try to get current URL
            current_url = driver.current_url
            if current_url and current_url != "data:,":
                msg += f"\n🔗 <a href='{current_url}'>Book Now</a>"
            
            send_telegram_msg(msg)
            print("✅ Alert sent to Telegram!")
            
            # Save screenshot
            screenshot_path = f"available_slots_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"📸 Screenshot saved: {screenshot_path}")
            return True
        else:
            print("❌ No available slots found")
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
