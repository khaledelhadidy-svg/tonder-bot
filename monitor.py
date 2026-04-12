import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HOME_URL = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en"
TARGET_URL = "https://reservation.frontdesksuite.com/toender/vielse/ReserveTime/TimeSelection?pageId=8d47364a-5e21-4e40-892d-e9f46878e18b&buttonId=073d59ae-ab0d-484a-90b1-e1f9b68a8843&culture=en"

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(msg_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

def check_availability():
    print("Starting Enhanced Session-Persistent Scan...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Apply stealth to avoid detection
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    try:
        # CRITICAL FIX: Navigate to HOME and wait for FULL load
        print("Step 1: Establishing session from Home page...")
        driver.get(HOME_URL)
        
        # Wait for the main form and marriage button to be present
        wait = WebDriverWait(driver, 15)
        main_form = wait.until(EC.presence_of_element_located((By.ID, "mainForm")))
        
        # Find and click the marriage button to generate proper session state
        print("Step 2: Clicking marriage selection button...")
        marriage_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='TimeSelection'], button[onclick*='TimeSelection']")))
        marriage_button.click()
        
        # Wait for navigation to complete
        time.sleep(3)
        
        # Now we should be on the TimeSelection page with valid session
        print("Step 3: Verifying calendar load...")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "date")))
        
        # Additional wait for dynamic content
        time.sleep(5)
        
        # Extract date blocks
        date_blocks = driver.find_elements(By.CLASS_NAME, "date.one-queue")
        
        if not date_blocks:
            # Fallback selector
            date_blocks = driver.find_elements(By.CSS_SELECTOR, ".date")
        
        available_dates = []
        full_dates = []
        no_slots_phrase = "No more available time slots"
        
        for block in date_blocks:
            try:
                header = block.find_element(By.CSS_SELECTOR, ".header-text")
                date_text = header.text.strip()
                
                # Check if this date has availability
                block_html = block.get_attribute('innerHTML')
                
                if no_slots_phrase not in block_html:
                    # Available slot found!
                    available_dates.append(date_text)
                    print(f"✅ AVAILABLE: {date_text}")
                    
                    # Try to extract time slots
                    time_slots = block.find_elements(By.CSS_SELECTOR, ".time-slot, [onclick*='selectTime']")
                    if time_slots:
                        print(f"   → {len(time_slots)} time slots available")
                else:
                    full_dates.append(date_text)
                    print(f"❌ FULL: {date_text}")
                    
            except Exception as e:
                print(f"Error parsing block: {e}")
                continue
        
        print(f"\n📊 SUMMARY: {len(available_dates)} available, {len(full_dates)} fully booked")
        
        # Send alert if any date is available
        if available_dates:
            msg = f"🚨 <b>WEDDING SLOT ALERT!</b>\n\n"
            msg += f"📅 Available dates:\n"
            for date in available_dates[:5]:  # Show first 5
                msg += f"  • {date}\n"
            msg += f"\n🔗 <a href='{driver.current_url}'>Book Now</a>"
            send_telegram_msg(msg)
            
            # Optional: Save screenshot of available slots
            screenshot_path = f"available_slots_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"📸 Screenshot saved: {screenshot_path}")
            
            return True
        else:
            print("❌ No available slots found")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Debug: Save page source for troubleshooting
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("📄 Debug HTML saved to debug_page.html")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    check_availability()
