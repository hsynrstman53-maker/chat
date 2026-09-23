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

# ساعت ایران
IRAN_TZ = timedelta(hours=3, minutes=30)
def iran_now():
    return datetime.utcnow() + IRAN_TZ

# ساخت کد یکتا
def make_code(fullname):
    # حرف‌های انگلیسی و عدد از اسم
    name_part = ''.join(e for e in fullname if e.isalnum())
    if not name_part:
        name_part = 'USER'
    # ۴ کاراکتر تصادفی
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{name_part[:15]}-{random_part}"

# دیتابیس: کاربران
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=iran_now)

# دیتابیس: پیام‌ها
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

# ثبت‌نام یا ورود
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    fullname = data.get('fullname', '').strip()
    if not fullname:
        return jsonify({'ok': False, 'error': 'اسم رو بنویس'})
    
    user = User.query.filter_by(fullname=fullname).first()
    if not user:
        # ساخت کد یکتا (تا وقتی که تکراری نباشه)
        code = make_code(fullname)
        while User.query.filter_by(code=code).first():
            code = make_code(fullname)
        user = User(fullname=fullname, code=code)
        db.session.add(user)
        db.session.commit()
    
    return jsonify({
        'ok': True,
        'user_id': user.id,
        'fullname': user.fullname,
        'code': user.code
    })

# ساخت QR برای یه کد
@app.route('/qr/<code>')
def make_qr(code):
    # لینک اسکن
    link = request.host_url + 'scan/' + code
    # ساخت QR
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# اسکن کردن کد
@app.route('/scan/<code>')
def scan(code):
    user = User.query.filter_by(code=code).first()
    if not user:
        return "کاربر پیدا نشد!", 404
    return render_template('index.html', scanned_code=code)

# گرفتن اطلاعات کاربر با کد
@app.route('/user-by-code/<code>')
def user_by_code(code):
    user = User.query.filter_by(code=code).first()
    if not user:
        return jsonify({'ok': False})
    return jsonify({'ok': True, 'user_id': user.id, 'fullname': user.fullname})

# فرستادن پیام
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

# گرفتن پیام‌ها
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

# گرفتن همه‌ی کاربران
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
