from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py


app = Flask(__name__)

@app.route('/generate_schedule', methods=['POST'])
def api_generate_schedule():
    data = request.json
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        result = generate_schedule(file_path)
        return jsonify(result)  # Returns {'schedule': [...]}
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True)


