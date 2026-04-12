import os
import time
import requests
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# The direct page URL
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

def count_no_slots_available(html_content):
    """
    Count occurrences of "No more available time slots" in the HTML
    Also returns list of dates that ARE available (no warning message)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Count warning messages directly
    warning_messages = soup.find_all('span', string='No more available time slots')
    count_warning = len(warning_messages)
    
    # Method 2: Count date blocks without warning messages (these would be available)
    date_blocks = soup.find_all('div', class_='date one-queue')
    
    available_dates = []
    for block in date_blocks:
        # Check if this block has the warning message
        warning = block.find('span', string='No more available time slots')
        if not warning:
            # No warning means slots are available!
            date_text = block.find('span', class_='header-text')
            if date_text:
                available_dates.append(date_text.text.strip())
    
    # Also try counting by text in warning-message divs
    warning_divs = soup.find_all('div', class_='warning-message')
    count_divs = len(warning_divs)
    
    print(f"  Found {count_warning} warning spans")
    print(f"  Found {count_divs} warning divs")
    print(f"  Found {len(date_blocks)} total date blocks")
    print(f"  Available dates: {len(available_dates)}")
    
    return max(count_warning, count_divs), available_dates

def get_page_with_session():
    """Fetch page with proper session handling"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    
    # First, visit the home page to establish session
    home_url = "https://reservation.frontdesksuite.com/toender/vielse/Home/Index?pageid=8d47364a-5e21-4e40-892d-e9f46878e18b&culture=en"
    print("  Establishing session via home page...")
    try:
        home_response = session.get(home_url, headers=headers, timeout=15)
        time.sleep(2)  # Let session cookies set
    except Exception as e:
        print(f"  ⚠️ Home page request failed: {e}")
    
    # Now fetch the target page
    print("  Fetching target page...")
    response = session.get(TARGET_URL, headers=headers, timeout=15)
    
    return response

def load_previous_count():
    """Load the previously stored slot count"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                data = f.read().strip().split(',')
                count = int(data[0])
                hash_val = data[1] if len(data) > 1 else ""
                return count, hash_val
            except:
                return None, None
    return None, None

def save_current_count(count, content_hash):
    """Save the current slot count and content hash"""
    with open(STATE_FILE, 'w') as f:
        f.write(f"{count},{content_hash}")

def get_content_hash(html_content):
    """Create a hash of relevant page content to detect changes"""
    # Only hash the date blocks to avoid false positives from timestamps
    soup = BeautifulSoup(html_content, 'html.parser')
    date_blocks = soup.find_all('div', class_='date one-queue')
    relevant_content = str(date_blocks)
    return hashlib.md5(relevant_content.encode()).hexdigest()

def check_availability():
    """Main monitoring function"""
    print(f"\n{'='*60}")
    print(f"🔍 Wedding Slot Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        # Fetch the page
        print("📡 Fetching page...")
        response = get_page_with_session()
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
        
        # Count the "No more available time slots"
        print("📊 Analyzing page content...")
        no_slots_count, available_dates = count_no_slots_available(response.text)
        
        # Get content hash for change detection
        content_hash = get_content_hash(response.text)
        
        # Load previous state
        previous_count, previous_hash = load_previous_count()
        
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
            save_current_count(no_slots_count, content_hash)
            return True
        
        # Check if count has changed (someone booked a slot)
        elif previous_count is not None and no_slots_count != previous_count:
            print(f"\n⚠️ SLOT COUNT CHANGED!")
            print(f"   Was: {previous_count}, Now: {no_slots_count}")
            
            # If count decreased, a slot was booked (bad for us)
            # If count increased, more slots became unavailable
            if no_slots_count < previous_count:
                # This could mean someone cancelled, making a slot available!
                msg = f"🔔 <b>POTENTIAL SLOT OPENING!</b>\n\n"
                msg += f"Available slot count changed from {previous_count} to {no_slots_count}\n\n"
                msg += f"This might mean a slot has become available!\n\n"
                msg += f"🔗 <a href='{TARGET_URL}'>Check Now</a>"
                send_telegram_msg(msg)
            
            save_current_count(no_slots_count, content_hash)
        
        elif previous_hash is not None and content_hash != previous_hash:
            print(f"\n⚠️ Page content changed (structure may have updated)")
            # Send notification about structural change
            msg = f"ℹ️ <b>Page Structure Changed</b>\n\n"
            msg += f"The wedding booking page has been updated.\n"
            msg += f"Current 'No slots' count: {no_slots_count}\n\n"
            msg += f"🔗 <a href='{TARGET_URL}'>Review Changes</a>"
            send_telegram_msg(msg)
            save_current_count(no_slots_count, content_hash)
        
        else:
            print(f"\n✅ No changes detected. All {no_slots_count} dates still fully booked.")
        
        return True
        
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_availability()
