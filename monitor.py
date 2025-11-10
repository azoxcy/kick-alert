import os
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
        print(f"Error sending Telegram message: {e}")
        return None

def check_kick_channel(channel):
    try:
        url = f"https://kick.com/api/v2/channels/{channel}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('livestream'):
                livestream = data['livestream']
                return {
                    'is_live': True,
                    'title': livestream.get('session_title', 'No title'),
                    'viewer_count': livestream.get('viewer_count', 0),
                    'thumbnail': livestream.get('thumbnail', {}).get('url', ''),
                    'started_at': livestream.get('created_at', '')
                }
        
        return {'is_live': False}
    except Exception as e:
        print(f"Error checking channel {channel}: {e}")
        return {'is_live': False}

def check_keyword_match(title, keywords):
    title_lower = title.lower()
    for keyword in keywords:
        if keyword.lower() in title_lower:
            return keyword
    return None

def start_monitoring():
    print("🚀 Monitor started!")
    
    while True:
        try:
            data = load_data()
            monitors = data.get('monitors', {})
            users = data.get('users', {})
            
            if not monitors:
                print("⏳ No monitors found, waiting...")
                time.sleep(120)
                continue
            
            print(f"🔍 Checking {len(monitors)} monitors...")
            
            for monitor_id, monitor in monitors.items():
                channel = monitor['channel']
                keywords = monitor['keywords']
                user_id = monitor['user_id']
                
                # Get user chat_id
                user = users.get(user_id, {})
                user_chat_id = user.get('chat_id')
                
                if not user_chat_id:
                    print(f"⚠️ No chat_id for user {user_id}")
                    continue
                
                # Check channel
                status = check_kick_channel(channel)
                
                if status['is_live']:
                    title = status['title']
                    matched_keyword = check_keyword_match(title, keywords)
                    
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
                            
                            # Send to user
                            send_telegram_message(user_chat_id, message)
                            print(f"✅ Notification sent to user {user_id} for {channel}")
                            
                            # Send to admin
                            if ADMIN_CHAT_ID:
                                admin_message = f"👑 <b>نسخة للمدير</b>\n{message}\n👤 <b>المستخدم:</b> {user.get('username', 'Unknown')}"
                                send_telegram_message(ADMIN_CHAT_ID, admin_message)
                            
                            SENT_NOTIFICATIONS[notification_key] = time.time()
            
            # Clean old notifications (after 6 hours)
            current_time = time.time()
            SENT_NOTIFICATIONS.clear()
            for key, timestamp in list(SENT_NOTIFICATIONS.items()):
                if current_time - timestamp > 21600:
                    del SENT_NOTIFICATIONS[key]
            
            print(f"✅ Check completed. Waiting 120 seconds...")
            time.sleep(120)
            
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            time.sleep(60)

if __name__ == '__main__':
    start_monitoring()
