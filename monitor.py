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
    """Check with full debugging"""
    try:
        url = f"https://kick.com/api/v2/channels/{channel}"
        
        print(f"   🔗 URL: {url}", flush=True)
        sys.stdout.flush()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://kick.com/',
            'Origin': 'https://kick.com'
        }
        
        print(f"   📤 Sending request...", flush=True)
        sys.stdout.flush()
        
        response = requests.get(url, headers=headers, timeout=15)
        
        print(f"   📥 Response Status: {response.status_code}", flush=True)
        print(f"   📏 Response Size: {len(response.content)} bytes", flush=True)
        sys.stdout.flush()
        
        # Print response headers
        print(f"   📋 Response Headers:", flush=True)
        for key, value in list(response.headers.items())[:5]:
            print(f"      {key}: {value}", flush=True)
        sys.stdout.flush()
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ JSON parsed successfully", flush=True)
                print(f"   🔑 JSON keys: {list(data.keys())}", flush=True)
                sys.stdout.flush()
                
                livestream = data.get('livestream')
                print(f"   📡 livestream exists: {livestream is not None}", flush=True)
                
                if livestream:
                    print(f"   📊 livestream keys: {list(livestream.keys())[:10]}", flush=True)
                    is_live = livestream.get('is_live')
                    print(f"   🎥 is_live value: {is_live}", flush=True)
                    sys.stdout.flush()
                    
                    if is_live:
                        title = livestream.get('session_title', 'No title')
                        print(f"   ✅ Stream is LIVE!", flush=True)
                        sys.stdout.flush()
                        
                        return {
                            'is_live': True,
                            'title': title,
                            'viewer_count': livestream.get('viewer_count', 0),
                            'thumbnail': livestream.get('thumbnail', {}).get('url', ''),
                            'started_at': livestream.get('created_at', '')
                        }
                
                print(f"   💤 Stream not live", flush=True)
                sys.stdout.flush()
                
            except json.JSONDecodeError as je:
                print(f"   ❌ JSON Error: {je}", flush=True)
                print(f"   📄 Response preview: {response.text[:200]}", flush=True)
                sys.stdout.flush()
                
        elif response.status_code == 403:
            print(f"   🚫 403 Forbidden!", flush=True)
            print(f"   📄 Response: {response.text[:500]}", flush=True)
            sys.stdout.flush()
            
        elif response.status_code == 404:
            print(f"   ❓ 404 Not Found - Channel may not exist", flush=True)
            sys.stdout.flush()
            
        else:
            print(f"   ❌ Unexpected status: {response.status_code}", flush=True)
            print(f"   📄 Response: {response.text[:300]}", flush=True)
            sys.stdout.flush()
        
        return {'is_live': False}
        
    except requests.exceptions.Timeout:
        print(f"   ⏰ Request timed out", flush=True)
        sys.stdout.flush()
        return {'is_live': False}
        
    except requests.exceptions.ConnectionError as ce:
        print(f"   🔌 Connection error: {ce}", flush=True)
        sys.stdout.flush()
        return {'is_live': False}
        
    except Exception as e:
        print(f"   ❌ Exception: {type(e).__name__}: {e}", flush=True)
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
                
                print(f"\n   📺 Channel: {channel}", flush=True)
                sys.stdout.flush()
                
                user = users.get(user_id, {})
                user_chat_id = user.get('chat_id')
                
                if not user_chat_id:
                    print(f"   ⚠️ No chat_id for user", flush=True)
                    sys.stdout.flush()
                    continue
                
                status = check_kick_channel(channel)
                
                if status['is_live']:
                    title = status['title']
                    print(f"\n   ✅ LIVE: {title}", flush=True)
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
                            print(f"   ⏭️ Already sent notification", flush=True)
                            sys.stdout.flush()
                    else:
                        print(f"   ❌ No keyword match", flush=True)
                        sys.stdout.flush()
                else:
                    print(f"   💤 Channel offline\n", flush=True)
                    sys.stdout.flush()
            
            current_time = time.time()
            for key, timestamp in list(SENT_NOTIFICATIONS.items()):
                if current_time - timestamp > 21600:
                    del SENT_NOTIFICATIONS[key]
            
            print(f"\n✅ Check done. Waiting 120s...\n", flush=True)
            sys.stdout.flush()
            time.sleep(120)
            
        except Exception as e:
            print(f"❌ Loop error: {type(e).__name__}: {e}", flush=True)
            sys.stdout.flush()
            time.sleep(60)

if __name__ == '__main__':
    start_monitoring()
