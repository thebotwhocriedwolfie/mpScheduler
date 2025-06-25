from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py
from flask_cors import CORS  #import cors
from flask import Flask, request, jsonify, send_from_directory


app = Flask(__name__)
CORS(app) #enable cors

#function to get dataset info to display
def get_counts(file_path):
    # Load data from Excel file into DataFrames
    xls = pd.ExcelFile(file_path)
    
    # Load tables and get counts
    return {
        'teacher_count': len(pd.read_excel(xls, 'Teacher Table').index),
        'classes_count': len(pd.read_excel(xls, 'Class Table').index),
        'rooms_count': len(pd.read_excel(xls, 'Room Table').index)
    }

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

#display counts
@app.route('/counts', methods=['GET'])  # get api route
def api_get_counts():
    file_path = request.args.get('file_path')  # GET requests use args, not json
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        counts = get_counts(file_path)
        return jsonify(counts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)


