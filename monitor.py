import os
import sys
import time
import json
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

DATA_FILE = 'data.json'
SENT_NOTIFICATIONS = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {'users': {}, 'monitors': {}}

def send_telegram_message(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Telegram Error: {e}", flush=True)
        sys.stdout.flush()
        return None

def check_kick_channel(channel):
    try:
        url = f"https://kick.com/api/v2/channels/{channel}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://kick.com/',
            'Origin': 'https://kick.com'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"   🌐 API Status: {response.status_code}", flush=True)
        sys.stdout.flush()
        
        if response.status_code == 200:
            data = response.json()
            livestream = data.get('livestream')
            
            print(f"   📡 Has livestream: {livestream is not None}", flush=True)
            sys.stdout.flush()
            
            if livestream and livestream.get('is_live'):
                print(f"   🎥 is_live: True", flush=True)
                sys.stdout.flush()
                
                return {
                    'is_live': True,
                    'title': livestream.get('session_title', 'No title'),
                    'viewer_count': livestream.get('viewer_count', 0),
                    'thumbnail': livestream.get('thumbnail', {}).get('url', ''),
                    'started_at': livestream.get('created_at', '')
                }
            else:
                print(f"   💤 is_live: False or No livestream", flush=True)
                sys.stdout.flush()
        else:
            print(f"   ❌ API Error: Status {response.status_code}", flush=True)
            sys.stdout.flush()
        
        return {'is_live': False}
    except Exception as e:
        print(f"❌ Exception: {e}", flush=True)
        sys.stdout.flush()
        return {'is_live': False}

def check_keyword_match(title, keywords):
    title_lower = title.lower()
    for keyword in keywords:
        if keyword.lower() in title_lower:
            return keyword
    return None

def start_monitoring():
    print("🚀 Monitor started!", flush=True)
    sys.stdout.flush()
    
    while True:
        try:
            data = load_data()
            monitors = data.get('monitors', {})
            users = data.get('users', {})
            
            if not monitors:
                print("⏳ No monitors, waiting 120s...", flush=True)
                sys.stdout.flush()
                time.sleep(120)
                continue
            
            print(f"🔍 Checking {len(monitors)} monitors...", flush=True)
            sys.stdout.flush()
            
            for monitor_id, monitor in monitors.items():
                channel = monitor['channel']
                keywords = monitor['keywords']
                user_id = monitor['user_id']
                
                print(f"   📺 Channel: {channel}", flush=True)
                sys.stdout.flush()
                
                user = users.get(user_id, {})
                user_chat_id = user.get('chat_id')
                
                if not user_chat_id:
                    print(f"   ⚠️ No chat_id", flush=True)
                    sys.stdout.flush()
                    continue
                
                status = check_kick_channel(channel)
                
                if status['is_live']:
                    title = status['title']
                    print(f"   ✅ LIVE: {title}", flush=True)
                    sys.stdout.flush()
                    
                    matched_keyword = check_keyword_match(title, keywords)
                    print(f"   🔑 Keywords: {keywords}", flush=True)
                    print(f"   🎯 Matched: {matched_keyword}", flush=True)
                    sys.stdout.flush()
                    
                    if matched_keyword:
                        notification_key = f"{channel}_{title}"
                        
                        if notification_key not in SENT_NOTIFICATIONS:
                            message = f"""
🔔 <b>تنبيه جديد!</b>

📺 <b>القناة:</b> {channel}
📝 <b>العنوان:</b> {title}
✅ <b>تطابق الكلمة:</b> {matched_keyword}
👁️ <b>المشاهدين:</b> {status['viewer_count']}
🕐 <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔗 <a href="https://kick.com/{channel}">شاهد البث</a>
"""
                            
                            send_telegram_message(user_chat_id, message)
                            print(f"   📤 Notification sent!", flush=True)
                            sys.stdout.flush()
                            
                            if ADMIN_CHAT_ID:
                                admin_msg = f"👑 <b>نسخة للمدير</b>\n{message}\n👤 <b>المستخدم:</b> {user.get('username', 'Unknown')}"
                                send_telegram_message(ADMIN_CHAT_ID, admin_msg)
                            
                            SENT_NOTIFICATIONS[notification_key] = time.time()
                        else:
                            print(f"   ⏭️ Already sent", flush=True)
                            sys.stdout.flush()
                    else:
                        print(f"   ❌ No keyword match", flush=True)
                        sys.stdout.flush()
                else:
                    print(f"   💤 Offline", flush=True)
                    sys.stdout.flush()
            
            current_time = time.time()
            for key, timestamp in list(SENT_NOTIFICATIONS.items()):
                if current_time - timestamp > 21600:
                    del SENT_NOTIFICATIONS[key]
            
            print(f"✅ Done. Waiting 120s...", flush=True)
            sys.stdout.flush()
            time.sleep(120)
            
        except Exception as e:
            print(f"❌ Loop error: {e}", flush=True)
            sys.stdout.flush()
            time.sleep(60)

if __name__ == '__main__':
    start_monitoring()
