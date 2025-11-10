import requests
import json
import os
import time
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

USERS_FILE = 'data/users.json'
MONITORS_FILE = 'data/monitors.json'
HISTORY_FILE = 'data/history.json'

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return {} if 'users' in filename or 'monitors' in filename else []

def save_json(filename, data):
    os.makedirs('data', exist_ok=True)
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def send_telegram_message(chat_id, message):
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ No bot token configured")
        return False
    
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        if result.get('ok'):
            print(f"✅ Message sent to {chat_id}")
            return True
        else:
            print(f"❌ Failed to send: {result}")
            return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

def check_kick_stream(channel):
    try:
        url = f'https://kick.com/api/v2/channels/{channel}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            livestream = data.get('livestream')
            
            if livestream and livestream.get('is_live'):
                return {
                    'is_live': True,
                    'title': livestream.get('session_title', ''),
                    'viewer_count': livestream.get('viewer_count', 0)
                }
        
        return {'is_live': False, 'title': '', 'viewer_count': 0}
    except Exception as e:
        print(f"❌ Error checking {channel}: {e}")
        return {'is_live': False, 'title': '', 'viewer_count': 0}

def check_all_monitors():
    print("\n" + "="*50)
    print(f"🔍 Starting monitor check at {datetime.now().strftime('%I:%M %p')}")
    print("="*50)
    
    monitors = load_json(MONITORS_FILE)
    users = load_json(USERS_FILE)
    history = load_json(HISTORY_FILE)
    
    if not monitors:
        print("⚠️ No monitors found")
        return
    
    print(f"📊 Checking {len(monitors)} monitors...")
    
    notifications_sent = 0
    
    for monitor_id, monitor in monitors.items():
        if monitor.get('status') != 'active':
            continue
        
        channel = monitor['channel']
        print(f"\n📺 Checking: {channel}")
        
        stream_info = check_kick_stream(channel)
        
        if not stream_info['is_live']:
            print(f"   ⚪ Not live")
            continue
        
        current_title = stream_info['title']
        last_title = monitor.get('last_title', '')
        
        print(f"   🔴 Live: {current_title}")
        
        if current_title and current_title != last_title:
            keywords = monitor.get('keywords', [])
            matched_keyword = None
            
            for keyword in keywords:
                if keyword.lower() in current_title.lower():
                    matched_keyword = keyword
                    break
            
            if matched_keyword:
                print(f"   ✅ Keyword matched: {matched_keyword}")
                
                user_id = monitor['user_id']
                chat_id = None
                username = 'Unknown'
                
                if user_id == 'admin':
                    chat_id = ADMIN_CHAT_ID
                    username = 'Admin'
                elif user_id in users:
                    chat_id = users[user_id].get('chat_id')
                    username = users[user_id].get('username', 'Unknown')
                
                if chat_id:
                    message = f"🔔 <b>تنبيه جديد!</b>\n\n"
                    message += f"📺 القناة: <b>{channel}</b>\n"
                    message += f"📝 العنوان: {current_title}\n"
                    message += f"✅ تطابق الكلمة: <b>{matched_keyword}</b>\n"
                    message += f"👥 المشاهدين: {stream_info['viewer_count']}\n"
                    message += f"🕐 الوقت: {datetime.now().strftime('%I:%M %p')}\n\n"
                    message += f"🔗 <a href='https://kick.com/{channel}'>شاهد البث</a>"
                    
                    if send_telegram_message(chat_id, message):
                        notifications_sent += 1
                        
                        if user_id != 'admin' and ADMIN_CHAT_ID:
                            admin_message = f"📊 <b>تنبيه من المستخدم:</b> {username}\n\n" + message
                            send_telegram_message(ADMIN_CHAT_ID, admin_message)
                        
                        history.append({
                            'monitor_id': monitor_id,
                            'user_id': user_id,
                            'channel': channel,
                            'title': current_title,
                            'keyword': matched_keyword,
                            'timestamp': datetime.now().isoformat()
                        })
            
            monitor['last_title'] = current_title
    
    save_json(MONITORS_FILE, monitors)
    save_json(HISTORY_FILE, history[-100:])
    
    print("\n" + "="*50)
    print(f"✅ Check complete! Sent {notifications_sent} notifications")
    print("="*50 + "\n")

if __name__ == '__main__':
    print("🚀 Kick Monitor Started")
    print(f"⏰ Checking every 2 minutes...")
    
    while True:
        try:
            check_all_monitors()
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
        
        print("💤 Sleeping for 2 minutes...")
        time.sleep(120)
