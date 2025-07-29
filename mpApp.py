from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py
from allocation import run_teacher_assignment #import function from allocation.py
from flask_cors import CORS  #import cors
from flask import Flask, request, jsonify, send_from_directory
from io import BytesIO
import pandas as pd
import requests
import os
import json


app = Flask(__name__)
CORS(app) #enable cors


@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    file_path = "preferences.json"
    data = request.get_json()

    # Validate payload
    if not data or 'TeacherId' not in data:
        return jsonify({"status": "error", "message": "Missing TeacherId"}), 400

    # Initialize or load existing preferences
    try:
        existing_data = {}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
                # Convert old list format to dict if needed
                if isinstance(existing_data, list):
                    existing_data = {item['TeacherId']: item for item in existing_data}
    except Exception as e:
        print(f"Warning: Reset corrupted preferences. Error: {e}")
        existing_data = {}

    # Update preferences (dict format)
    teacher_id = data['TeacherId']
    existing_data[teacher_id] = {
        'TeacherId': teacher_id,  # Explicitly include for reference
        'unavailable_days': data.get('unavailableDays', []),
        'unavailable_slots': data.get('unavailableSlots', []),
        'full_day': data.get('fullDay', False)
    }

    # Atomic write (prevents corruption)
    temp_path = f"{file_path}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(existing_data, f, indent=2)
    os.replace(temp_path, file_path)

    return jsonify({"status": "success"})


# Serve the static CSV file
@app.route('/Allocations.csv')
def serve_allocations_csv():
    try:
        return send_from_directory('.', 'Allocations.csv')
    except Exception as e:
        return jsonify({'error': 'Allocations file not found'}), 404

#get allocation results
@app.route('/get_allocations', methods=['GET'])
def get_allocations():
    file_path = request.args.get('file_path')
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    try:
        csv_path = "Allocations.csv"
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No allocations found. Please run allocation first.'}), 404
            
        df = pd.read_csv(csv_path)
        return jsonify(df.to_dict('records'))  # Return as JSON properly
    except Exception as e:
        return jsonify({'error': str(e)}), 500
def get_counts(file_path):
    if file_path.startswith("http"):
        response = requests.get(file_path)
        response.raise_for_status()
        xls = pd.ExcelFile(BytesIO(response.content))
    else:
        xls = pd.ExcelFile(file_path)

    return {
        'teacher_count': len(pd.read_excel(xls, 'Teacher Table').index),
        'classes_count': len(pd.read_excel(xls, 'Class Table').index),
        'rooms_count': len(pd.read_excel(xls, 'Room Table').index)
    }



@app.route('/scheduler.html') #HTML page route
def serve_scheduler():
    return send_from_directory("public", "scheduler.html")

@app.route('/assign.html') #HTML page route
def serve_allocation():
    return send_from_directory("public", "assign.html")

@app.route('/teacherpref.html') #HTML page route
def preference_form():
    return send_from_directory("public", "teacherpref.html")

@app.route('/assign_teachers', methods=['POST'])
def api_assign_teachers():
    data = request.json
    file_path = data.get('file_path')  # Semester file selected from frontend

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        output_df = run_teacher_assignment(file_path)
        #overite static allocation csv file
        output_df.to_csv("Allocations.csv",index=False)
        #return summary: number of teachers used, total allocations
        summary = {
            'assignments_count': len(output_df),
            'unique_teachers': len(output_df['TeacherId'].unique())
        }
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#generate schedule api 
@app.route('/generate_schedule', methods=['POST'])
def api_generate_schedule():
    data = request.json
    file_path = data.get('file_path')
    assignment_csv = data.get('assignment_csv', "Allocations.csv")
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        # Load preferences if available
        preferences = []
        if os.path.exists('preferences.json'):
            with open('preferences.json', 'r') as f:
                preferences = json.load(f)
        
        result = generate_schedule(file_path, assignment_csv, preferences)
        
        #Print each entry for debug
        for entry in result['schedule']:
            print(entry)

        return jsonify(result)
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


