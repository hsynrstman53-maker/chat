from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

messages = []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    name = data.get('name', 'ناشناس')
    text = data.get('text', '')
    if text:
        messages.append({'name': name, 'text': text})
    return jsonify({'ok': True})

@app.route('/messages')
def get_messages():
    return jsonify(messages)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
