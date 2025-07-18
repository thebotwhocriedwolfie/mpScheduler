from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py
from allocation import run_teacher_assignment #import function from allocation.py
from flask_cors import CORS  #import cors
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

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


@app.route('/generate_schedule', methods=['POST'])
def api_generate_schedule():
    data = request.json
    file_path = data.get('file_path')
    assignment_csv = data.get('assignment_csv', "Allocations.csv")

    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    try:
        result = generate_schedule(file_path, assignment_csv)  # returns a Python dict of logs
        return jsonify(result)  # this is already JSON-friendly
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#link files (uploaded on frontend to be accessible in the backend)
function runFullScheduleFlow() {
    const selectedFile = document.getElementById("fileDropdown").value;

    fetch('/assign_teachers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: selectedFile })
    })
    .then(response => response.json())
    .then(assignData => {
        console.log("Teacher assignments:", assignData);

        // Step 2: Generate schedule
        return fetch('/generate_schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: selectedFile })
        });
    })
    .then(response => response.json())
    .then(scheduleData => {
        console.log("Schedule generated:", scheduleData);
        // Update UI with final results
    })
    .catch(error => {
        console.error("Error in full flow:", error);
    });
}


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


