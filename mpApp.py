from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py
from allocation import run_teacher_assignment #import function from allocation.py
from flask_cors import CORS  #import cors
from flask import Flask, request, jsonify, send_from_directory
from io import BytesIO
import pandas as pd
import requests
import os


app = Flask(__name__)
CORS(app) #enable cors

#save teacher preferences in json file (preferences.json)
@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    try:
        # Get the JSON data from the request
        data = request.json
        
        # Read existing data
        with open("public/preferences.json", 'r') as f:
            existing_data = json.load(f)

        print("🩺 Saving teacher preferences:")
        print("Full payload:", data)
        print("Type of unavailable_slots:", type(data.get("unavailableSlots")))
        print("Value of unavailable_slots:", data.get("unavailableSlots"))

        
        # Add new data
        existing_data.append(data)
        
        # Write back to file
        with open('preferences.json', 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        return jsonify({"status": "success", "message": "Preferences saved"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500




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

#get allocation results
@app.route('/get_allocations', methods=['GET'])
def get_allocations():
    file_path = request.args.get('file_path')

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        import os
        semester_name = os.path.basename(file_path).replace(".xlsx", "")
        csv_path = "Allocations.csv"

        df = pd.read_csv(csv_path)
        return df.to_json(orient='records')  # Returns rows as list of objects
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/scheduler.html') #HTML page route
def serve_scheduler():
    return send_from_directory("public", "scheduler.html")

@app.route('/assign.html') #HTML page route
def serve_allocation():
    return send_from_directory("public", "assign.html")

@app.route('/teacher_pref.html') #HTML page route
def preference_form():
    return send_from_directory("public", "teacher_pref.html")

@app.route('/assign_teachers', methods=['POST'])
def api_assign_teachers():
    data = request.json
    file_path = data.get('file_path')  # Semester file selected from frontend

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        output_df = run_teacher_assignment(file_path)
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


