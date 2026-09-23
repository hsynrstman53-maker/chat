from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ساعت ایران
IRAN_TZ = timedelta(hours=3, minutes=30)
def iran_now():
    return datetime.utcnow() + IRAN_TZ

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=iran_now)

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
        user = User(fullname=fullname)
        db.session.add(user)
        db.session.commit()
    return jsonify({'ok': True, 'user_id': user.id, 'fullname': user.fullname})

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
        'fullname': u.fullname
    } for u in users])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
