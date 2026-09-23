from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random
import string
import io
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
    text = db.Column(db.Text, nullable=False)
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
    return jsonify({'ok': True, 'user_id': user.id, 'fullname': user.fullname, 'code': user.code})

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

# اضافه کردن مخاطب
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

# گرفتن مخاطبین یه کاربر
@app.route('/contacts/<int:user_id>')
def get_contacts(user_id):
    contacts = Contact.query.filter_by(owner_id=user_id).all()
    result = []
    for c in contacts:
        u = User.query.get(c.contact_id)
        if u:
            result.append({'id': u.id, 'fullname': u.fullname})
    return jsonify(result)

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    user_id = data.get('user_id')
    text = data.get('text', '').strip()
    if not text or not user_id:
        return jsonify({'ok': False})
    msg = Message(user_id=user_id, text=text)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/messages/<int:user_id>')
def get_messages(user_id):
    msgs = Message.query.filter_by(user_id=user_id).order_by(Message.created_at).all()
    return jsonify([{
        'id': m.id,
        'user_id': m.user_id,
        'name': m.user.fullname,
        'text': m.text,
        'time': m.created_at.strftime('%H:%M')
    } for m in msgs])

@app.route('/users')
def get_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'fullname': u.fullname,
        'code': u.code
    } for u in users])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
