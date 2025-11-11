from flask import Flask, render_template, request, redirect, session, jsonify
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')

DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {'users': {}, 'monitors': {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def init_admin():
    data = load_data()
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    admin_chat_id = os.environ.get('ADMIN_CHAT_ID', '')
    
    if 'admin' not in data['users']:
        data['users']['admin'] = {
            'username': admin_username,
            'password': admin_password,
            'chat_id': admin_chat_id,
            'is_admin': True,
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        save_data(data)

# Initialize admin on startup
init_admin()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    data = load_data()
    for user_id, user in data['users'].items():
        if user['username'] == username and user['password'] == password:
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = user.get('is_admin', False)
            return redirect('/admin' if user.get('is_admin') else '/dashboard')
    
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('dashboard.html', 
                         username=session['username'],
                         is_admin=session.get('is_admin', False))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect('/dashboard')
    return render_template('admin.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/monitors', methods=['GET', 'POST'])
def monitors():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = load_data()
    user_id = session['user_id']
    
    if request.method == 'GET':
        user_monitors = {k: v for k, v in data['monitors'].items() if v['user_id'] == user_id}
        return jsonify(user_monitors)
    
    if request.method == 'POST':
        channel = request.json.get('channel', '').strip()
        keywords = request.json.get('keywords', '').strip()
        
        if not channel or not keywords:
            return jsonify({'error': 'Missing data'}), 400
        
        keywords_list = [k.strip() for k in keywords.split(',')]
        
        monitor_id = f"{user_id}_{channel}_{datetime.now().timestamp()}"
        data['monitors'][monitor_id] = {
            'user_id': user_id,
            'channel': channel,
            'keywords': keywords_list,
            'created_at': datetime.now().isoformat()
        }
        save_data(data)
        return jsonify({'success': True})

@app.route('/api/monitors/<monitor_id>', methods=['DELETE'])
def delete_monitor(monitor_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = load_data()
    if monitor_id in data['monitors']:
        if data['monitors'][monitor_id]['user_id'] == session['user_id'] or session.get('is_admin'):
            del data['monitors'][monitor_id]
            save_data(data)
            return jsonify({'success': True})
    
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/users', methods=['GET', 'POST'])
def users():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = load_data()
    
    if request.method == 'GET':
        users_with_counts = {}
        for user_id, user in data['users'].items():
            if user_id == 'admin':
                continue
            monitor_count = sum(1 for m in data['monitors'].values() if m['user_id'] == user_id)
            users_with_counts[user_id] = {**user, 'monitor_count': monitor_count}
        return jsonify(users_with_counts)
    
    if request.method == 'POST':
        username = request.json.get('username', '').strip()
        password = request.json.get('password', '').strip()
        chat_id = request.json.get('chat_id', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Missing data'}), 400
        
        user_id = f"user_{datetime.now().timestamp()}"
        data['users'][user_id] = {
            'username': username,
            'password': password,
            'chat_id': chat_id,
            'is_admin': False,
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        save_data(data)
        return jsonify({'success': True})

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = load_data()
    if user_id in data['users'] and user_id != 'admin':
        del data['users'][user_id]
        data['monitors'] = {k: v for k, v in data['monitors'].items() if v['user_id'] != user_id}
        save_data(data)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
