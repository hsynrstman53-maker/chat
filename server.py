from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random
import string
import io
import base64
import qrcode

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

IRAN_TZ = timedelta(hours=3, minutes=30)
def iran_now():
    return datetime.utcnow() + IRAN_TZ

def make_code(fullname):
    name_part = ''.join(e for e in fullname if e.isalnum())
    if not name_part:
        name_part = 'USER'
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{name_part[:15]}-{random_part}"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    dark_mode = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime, default=iran_now)
    created_at = db.Column(db.DateTime, default=iran_now)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=iran_now)
    __table_args__ = (db.UniqueConstraint('owner_id', 'contact_id'),)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, default='')
    msg_type = db.Column(db.String(20), default='text')  # text, voice, image
    media_data = db.Column(db.Text, default='')  # base64
    reaction = db.Column(db.String(10), default='')
    seen = db.Column(db.Boolean, default=False)
    deleted_for_all = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=iran_now)
    user = db.relationship('User', backref='messages')

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    fullname = data.get('fullname', '').strip()
    if not fullname:
        return jsonify({'ok': False, 'error': 'اسم رو بنویس'})
    user = User.query.filter_by(fullname=fullname).first()
    if not user:
        code = make_code(fullname)
        while User.query.filter_by(code=code).first():
            code = make_code(fullname)
        user = User(fullname=fullname, code=code)
        db.session.add(user)
        db.session.commit()
    user.last_seen = iran_now()
    db.session.commit()
    return jsonify({
        'ok': True, 'user_id': user.id,
        'fullname': user.fullname, 'code': user.code,
        'dark_mode': user.dark_mode
    })

@app.route('/change-name', methods=['POST'])
def change_name():
    data = request.json
    user_id = data.get('user_id')
    new_name = data.get('new_name', '').strip()
    if not user_id or not new_name:
        return jsonify({'ok': False, 'error': 'اسم رو بنویس'})
    existing = User.query.filter_by(fullname=new_name).first()
    if existing and existing.id != user_id:
        return jsonify({'ok': False, 'error': 'این اسم قبلاً استفاده شده'})
    user = User.query.get(user_id)
    if user:
        user.fullname = new_name
        db.session.commit()
        return jsonify({'ok': True, 'fullname': new_name})
    return jsonify({'ok': False})

@app.route('/toggle-theme', methods=['POST'])
def toggle_theme():
    data = request.json
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    if user:
        user.dark_mode = not user.dark_mode
        db.session.commit()
        return jsonify({'ok': True, 'dark_mode': user.dark_mode})
    return jsonify({'ok': False})

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    data = request.json
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'ok': False})
    user = User.query.get(user_id)
    if user:
        user.last_seen = iran_now()
        db.session.commit()
    return jsonify({'ok': True})

@app.route('/user-status/<int:user_id>')
def user_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False})
    diff = (iran_now() - user.last_seen).total_seconds()
    online = diff < 30
    return jsonify({
        'ok': True, 'online': online,
        'last_seen': user.last_seen.strftime('%H:%M')
    })

@app.route('/qr/<code>')
def make_qr(code):
    link = request.host_url + 'scan/' + code
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/scan/<code>')
def scan(code):
    return render_template('index.html', scanned_code=code)

@app.route('/user-by-code/<code>')
def user_by_code(code):
    user = User.query.filter_by(code=code).first()
    if not user:
        return jsonify({'ok': False})
    return jsonify({'ok': True, 'user_id': user.id, 'fullname': user.fullname})

@app.route('/add-contact', methods=['POST'])
def add_contact():
    data = request.json
    owner_id = data.get('owner_id')
    contact_id = data.get('contact_id')
    if not owner_id or not contact_id or owner_id == contact_id:
        return jsonify({'ok': False})
    exists = Contact.query.filter_by(owner_id=owner_id, contact_id=contact_id).first()
    if not exists:
        c = Contact(owner_id=owner_id, contact_id=contact_id)
        db.session.add(c)
        db.session.commit()
    return jsonify({'ok': True})

@app.route('/contacts/<int:user_id>')
def get_contacts(user_id):
    contacts = Contact.query.filter_by(owner_id=user_id).all()
    result = []
    for c in contacts:
        u = User.query.get(c.contact_id)
        if u:
            diff = (iran_now() - u.last_seen).total_seconds()
            online = diff < 30
            result.append({
                'id': u.id, 'fullname': u.fullname,
                'online': online,
                'last_seen': u.last_seen.strftime('%H:%M')
            })
    return jsonify(result)

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    user_id = data.get('user_id')
    text = data.get('text', '').strip()
    msg_type = data.get('msg_type', 'text')
    media_data = data.get('media_data', '')
    if not user_id:
        return jsonify({'ok': False})
    if msg_type == 'text' and not text:
        return jsonify({'ok': False})
    msg = Message(user_id=user_id, text=text, msg_type=msg_type, media_data=media_data)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True, 'msg_id': msg.id})

@app.route('/messages/<int:user_id>')
def get_messages(user_id):
    msgs = Message.query.filter_by(user_id=user_id).order_by(Message.created_at).all()
    result = []
    for m in msgs:
        if m.deleted_for_all:
            result.append({
                'id': m.id, 'user_id': m.user_id,
                'name': m.user.fullname,
                'text': '🚫 این پیام حذف شد',
                'msg_type': 'deleted',
                'time': m.created_at.strftime('%H:%M'),
                'reaction': '', 'seen': m.seen
            })
        else:
            result.append({
                'id': m.id, 'user_id': m.user_id,
                'name': m.user.fullname,
                'text': m.text, 'msg_type': m.msg_type,
                'media_data': m.media_data,
                'time': m.created_at.strftime('%H:%M'),
                'reaction': m.reaction, 'seen': m.seen
            })
    return jsonify(result)

@app.route('/mark-seen/<int:user_id>', methods=['POST'])
def mark_seen(user_id):
    msgs = Message.query.filter_by(user_id=user_id, seen=False).all()
    for m in msgs:
        m.seen = True
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/delete-message', methods=['POST'])
def delete_message():
    data = request.json
    msg_id = data.get('msg_id')
    for_all = data.get('for_all', False)
    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'ok': False})
    if for_all:
        if msg.seen:
            return jsonify({'ok': False, 'error': 'پیام دیده شده، فقط برای خودت می‌تونی پاک کنی'})
        msg.deleted_for_all = True
        msg.text = ''
        msg.media_data = ''
        db.session.commit()
    else:
        # فقط برای خودم - یعنی از دید من پاک میشه
        # ساده: پیام رو کلاً حذف می‌کنیم (چون سرور فقط یه نسخه داره)
        db.session.delete(msg)
        db.session.commit()
    return jsonify({'ok': True})

@app.route('/react', methods=['POST'])
def react():
    data = request.json
    msg_id = data.get('msg_id')
    reaction = data.get('reaction', '')
    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'ok': False})
    msg.reaction = reaction
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/search/<int:user_id>')
def search(user_id):
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    msgs = Message.query.filter(
        Message.user_id == user_id,
        Message.text.contains(q),
        Message.deleted_for_all == False
    ).order_by(Message.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': m.id,
        'text': m.text,
        'name': m.user.fullname,
        'time': m.created_at.strftime('%H:%M')
    } for m in msgs])

@app.route('/users')
def get_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id, 'fullname': u.fullname, 'code': u.code
    } for u in users])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
