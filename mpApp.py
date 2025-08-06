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

# For Teacher Preference form 
@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    file_path = "preferences.json" # Saved to json file
    data = request.get_json()

    # Validate payload
    if not data or 'TeacherId' not in data: #error check for data consistency
        return jsonify({"status": "error", "message": "Missing TeacherId"}), 400

    #Initialize or load existing preferences
    try:
        existing_data = {}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
                # Error check -> convert old list format to dict if its a list since function uses dict
                if isinstance(existing_data, list):
                    existing_data = {item['TeacherId']: item for item in existing_data}
    except Exception as e:
        print(f"Warning: Reset corrupted preferences. Error: {e}")
        existing_data = {}

    #Update preferences (dict format)
    teacher_id = data['TeacherId']
    existing_data[teacher_id] = {
        'TeacherId': teacher_id,  #explicitly include for reference
        'unavailable_days': data.get('unavailableDays', []),
        'unavailable_slots': data.get('unavailableSlots', []),
        'full_day': data.get('fullDay', False)
    }

    #prevent corruption
    temp_path = f"{file_path}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(existing_data, f, indent=2)
    os.replace(temp_path, file_path)

    return jsonify({"status": "success"})


# Serve the static allocation CSV file 
@app.route('/Allocations.csv')
def serve_allocations_csv():
    try:
        return send_from_directory('.', 'Allocations.csv') 
    except Exception as e:
        return jsonify({'error': 'Allocations file not found'}), 404

#get allocation results in assign.html (view assignments button)
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


# static selectedFile
@app.route('/SelectedFile.json')
def serve_selected_file():
    try:
        return send_from_directory('.', 'SelectedFile.json')
    except Exception as e:
        return jsonify({'error': 'Selected file info not found'}), 404

#Get selected file
@app.route('/get_selected_file', methods=['GET'])
def get_selected_file():
    try:
        json_path = "SelectedFile.json"
        if not os.path.exists(json_path):
            return jsonify({'error': 'No file selection found. Please run allocation first.'}), 404
            
        with open(json_path, 'r') as f:
            file_info = json.load(f)
            
        return jsonify(file_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#HTML Routes
@app.route('/scheduler.html') #scheduler page route
def serve_scheduler():
    return send_from_directory("public", "scheduler.html")

@app.route('/assign.html') #allocation page route
def serve_allocation():
    return send_from_directory("public", "assign.html")

@app.route('/teacherpref.html') #teacher preference form page route
def preference_form():
    return send_from_directory("public", "teacherpref.html")

#Allocation.py api for assign teacher function
@app.route('/assign_teachers', methods=['POST'])
def api_assign_teachers():
    data = request.json
    file_path = data.get('file_path')
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400 
    
    try:
        result = run_teacher_assignment(file_path) #call function in allocation.py
        output_df = result['assignments_df']
        errors = result['errors'] #get error
        
        # Save the assignments to CSV
        output_df.to_csv("Allocations.csv", index=False)
        
        # Prepare response data
        response_data = {
            'success': True,
            'assignments_count': len(output_df),
            'unique_teachers': len(output_df['TeacherId'].unique()) if len(output_df) > 0 else 0,
            'total_classes_subjects': len(output_df) + len(errors),
            'unassigned_count': len(errors),
            'errors': errors,
            'has_errors': len(errors) > 0
        }
        
        # Save selected file info
        selected_file_info = {
            'file_path': file_path,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        with open("SelectedFile.json", "w") as f:
            json.dump(selected_file_info, f, indent=2)
        
        # Check if there are too many errors (insufficient teachers scenario)
        total_required = response_data['total_classes_subjects']
        assigned = response_data['assignments_count']
        
        if assigned == 0:
            # No assignments made at all
            return jsonify({
                'success': False,
                'error': 'INSUFFICIENT_TEACHERS',
                'message': 'No teachers could be assigned to any classes. Please check teacher qualifications and availability.',
                'details': {
                    'total_required': total_required,
                    'assigned': 0,
                    'errors': errors[:5]  # Show first 5 errors as examples
                }
            }), 422  # 422 Unprocessable data
        
        elif len(errors) > assigned:
            # More failures than successes - likely insufficient teachers
            return jsonify({
                'success': False,
                'error': 'INSUFFICIENT_TEACHERS',
                'message': f'Only {assigned} out of {total_required} assignments could be made. Insufficient qualified teachers available.',
                'details': {
                    'total_required': total_required,
                    'assigned': assigned,
                    'unassigned': len(errors),
                    'errors': errors[:10]  #Show first 10 errors as examples
                }
            }), 422
        
        else:
            # Successful with some warnings
            return jsonify(response_data), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'SERVER_ERROR',
            'message': f'Server error occurred: {str(e)}'
        }), 500

   

#generate schedule api 
@app.route('/generate_schedule', methods=['POST'])
def api_generate_schedule():
    data = request.json
    file_path = data.get('file_path')
    assignment_csv = data.get('assignment_csv', "Allocations.csv")
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        #Check if selected file matches the one used for allocations
        if os.path.exists("SelectedFile.json"):
            with open("SelectedFile.json", "r") as f:
                selected_file_info = json.load(f)
                
            if selected_file_info.get('file_path') and selected_file_info['file_path'] != file_path:
                return jsonify({
                    'error': f'Selected file does not match allocation file. Please create allocations for this file first.'
                }), 400
                
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



UPLOAD_FOLDER = 'powerappsCSV'  # Change from 'uploads' to 'powerappsCSV'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'Empty filename'}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    return jsonify({
        'message': f'File {file.filename} uploaded successfully.',
        'file_path': f'powerappsCSV/{file.filename}'  # Match dropdown values
    })

#for getting average hours -- get subject details
@app.route('/get_subject_table', methods=['GET'])
def get_subject_table():
    file_path = request.args.get('file_path')
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    try:
        if file_path.startswith("http"):
            response = requests.get(file_path)
            response.raise_for_status()
            xls = pd.ExcelFile(BytesIO(response.content))
        else:
            xls = pd.ExcelFile(file_path)
        
        # Read the Subject Table sheet
        subject_df = pd.read_excel(xls, 'Subject Table')
        
        # Convert to JSON
        return jsonify(subject_df.to_dict('records'))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)


