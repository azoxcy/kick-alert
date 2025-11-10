from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import json
import requests
import time
from datetime import datetime
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Data files
USERS_FILE = 'data/users.json'
MONITORS_FILE = 'data/monitors.json'
HISTORY_FILE = 'data/history.json'

# Initialize data directory
os.makedirs('data', exist_ok=True)

# Initialize data files if they don't exist
def init_data_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(MONITORS_FILE):
        with open(MONITORS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w') as f:
            json.dump([], f)

init_data_files()

# Helper functions
def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return {} if 'users' in filename or 'monitors' in filename else []

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_telegram_message(chat_id, message):
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, data=data, timeout=10)
        return response.json().get('ok', False)
    except:
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check admin login
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user_id'] = 'admin'
            session['username'] = username
            session['is_admin'] = True
            session['chat_id'] = ADMIN_CHAT_ID
            return redirect(url_for('dashboard'))
        
        # Check regular users
        users = load_json(USERS_FILE)
        for user_id, user_data in users.items():
            if user_data['username'] == username and user_data['password'] == hash_password(password):
                if user_data.get('status') == 'suspended':
                    return render_template('login.html', error='حسابك معلق مؤقتاً')
                session['user_id'] = user_id
                session['username'] = username
                session['is_admin'] = False
                session['chat_id'] = user_data.get('chat_id')
                return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='اسم المستخدم أو كلمة المرور خاطئة')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    is_admin = session.get('is_admin', False)
    return render_template('dashboard.html', is_admin=is_admin, username=session.get('username'))

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    return render_template('admin.html', username=session.get('username'))

# API Routes
@app.route('/api/monitors', methods=['GET'])
@login_required
def get_monitors():
    monitors = load_json(MONITORS_FILE)
    user_id = session['user_id']
    
    if session.get('is_admin'):
        return jsonify(monitors)
    else:
        user_monitors = {k: v for k, v in monitors.items() if v.get('user_id') == user_id}
        return jsonify(user_monitors)

@app.route('/api/monitors', methods=['POST'])
@login_required
def add_monitor():
    data = request.json
    channel = data.get('channel', '').strip()
    keywords = data.get('keywords', '').strip()
    
    if not channel or not keywords:
        return jsonify({'error': 'الرجاء ملء جميع الحقول'}), 400
    
    monitors = load_json(MONITORS_FILE)
    monitor_id = f"{session['user_id']}_{channel}_{int(time.time())}"
    
    monitors[monitor_id] = {
        'user_id': session['user_id'],
        'channel': channel,
        'keywords': [k.strip() for k in keywords.split(',')],
        'created_at': datetime.now().isoformat(),
        'last_title': '',
        'status': 'active'
    }
    
    save_json(MONITORS_FILE, monitors)
    return jsonify({'success': True, 'monitor_id': monitor_id})

@app.route('/api/monitors/<monitor_id>', methods=['DELETE'])
@login_required
def delete_monitor(monitor_id):
    monitors = load_json(MONITORS_FILE)
    
    if monitor_id not in monitors:
        return jsonify({'error': 'لم يتم العثور على المراقبة'}), 404
    
    # Check permissions
    if not session.get('is_admin') and monitors[monitor_id]['user_id'] != session['user_id']:
        return jsonify({'error': 'غير مصرح'}), 403
    
    del monitors[monitor_id]
    save_json(MONITORS_FILE, monitors)
    return jsonify({'success': True})

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = load_json(USERS_FILE)
    monitors = load_json(MONITORS_FILE)
    
    # Add monitor count to each user
    for user_id in users:
        user_monitors = [m for m in monitors.values() if m.get('user_id') == user_id]
        users[user_id]['monitor_count'] = len(user_monitors)
    
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
@admin_required
def add_user():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    chat_id = data.get('chat_id', '').strip()
    
    if not username or not password:
        return jsonify({'error': 'الرجاء ملء جميع الحقول المطلوبة'}), 400
    
    users = load_json(USERS_FILE)
    
    # Check if username exists
    for user_data in users.values():
        if user_data['username'] == username:
            return jsonify({'error': 'اسم المستخدم موجود مسبقاً'}), 400
    
    user_id = f"user_{int(time.time())}"
    users[user_id] = {
        'username': username,
        'password': hash_password(password),
        'chat_id': chat_id,
        'created_at': datetime.now().isoformat(),
        'status': 'active'
    }
    
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'user_id': user_id})

@app.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    users = load_json(USERS_FILE)
    
    if user_id not in users:
        return jsonify({'error': 'لم يتم العثور على المستخدم'}), 404
    
    # Delete user's monitors
    monitors = load_json(MONITORS_FILE)
    monitors = {k: v for k, v in monitors.items() if v.get('user_id') != user_id}
    save_json(MONITORS_FILE, monitors)
    
    # Delete user
    del users[user_id]
    save_json(USERS_FILE, users)
    
    return jsonify({'success': True})

@app.route('/api/check', methods=['POST'])
def check_streams():
    """Called by external cron job to check all streams"""
    monitors = load_json(MONITORS_FILE)
    users = load_json(USERS_FILE)
    history = load_json(HISTORY_FILE)
    
    for monitor_id, monitor in monitors.items():
        if monitor.get('status') != 'active':
            continue
        
        channel = monitor['channel']
        
        # Check Kick stream
        try:
            response = requests.get(f'https://kick.com/api/v2/channels/{channel}', timeout=10)
            if response.status_code == 200:
                data = response.json()
                current_title = data.get('livestream', {}).get('session_title', '')
                
                if current_title and current_title != monitor.get('last_title'):
                    # Check keywords
                    keywords = monitor.get('keywords', [])
                    matched_keyword = None
                    
                    for keyword in keywords:
                        if keyword.lower() in current_title.lower():
                            matched_keyword = keyword
                            break
                    
                    if matched_keyword:
                        # Send notification to user
                        user_id = monitor['user_id']
                        chat_id = None
                        
                        if user_id == 'admin':
                            chat_id = ADMIN_CHAT_ID
                        elif user_id in users:
                            chat_id = users[user_id].get('chat_id')
                        
                        if chat_id:
                            message = f"🔔 <b>تنبيه جديد!</b>\n\n"
                            message += f"📺 القناة: <b>{channel}</b>\n"
                            message += f"📝 العنوان: {current_title}\n"
                            message += f"✅ تطابق الكلمة: <b>{matched_keyword}</b>\n"
                            message += f"🕐 الوقت: {datetime.now().strftime('%I:%M %p')}\n\n"
                            message += f"🔗 <a href='https://kick.com/{channel}'>شاهد البث</a>"
                            
                            send_telegram_message(chat_id, message)
                            
                            # Send copy to admin if not admin
                            if user_id != 'admin' and ADMIN_CHAT_ID:
                                admin_message = f"📊 <b>تنبيه من المستخدم:</b> {users[user_id].get('username', 'Unknown')}\n\n" + message
                                send_telegram_message(ADMIN_CHAT_ID, admin_message)
                            
                            # Save to history
                            history.append({
                                'monitor_id': monitor_id,
                                'user_id': user_id,
                                'channel': channel,
                                'title': current_title,
                                'keyword': matched_keyword,
                                'timestamp': datetime.now().isoformat()
                            })
                    
                    # Update last title
                    monitor['last_title'] = current_title
        except:
            pass
    
    # Save updated data
    save_json(MONITORS_FILE, monitors)
    save_json(HISTORY_FILE, history[-100:])  # Keep last 100 entries
    
    return jsonify({'success': True, 'checked': len(monitors)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
