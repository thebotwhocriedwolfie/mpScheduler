from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py
from flask_cors import CORS  #import cors
from flask import Flask, request, jsonify, send_from_directory


app = Flask(__name__)
CORS(app) #enable cors

@app.route('/scheduler.html') #HTML page route
def serve_scheduler():
    return send_from_directory("public", "scheduler.html")

@app.route('/generate_schedule', methods=['POST']) #post api route
def api_generate_schedule(): #call the scheduler
    data = request.json
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        result = generate_schedule(file_path)
        return jsonify(result)  # Returns schedule results
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True)


