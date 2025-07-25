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

# One Drive Sycnced Folder Path
ONE_DRIVE_FOLDER = r"C:\Users\kiirt\OneDrive - Temasek Polytechnic\MP_Shared_Files\powerappsCSV"

# Then modify your list_files endpoint like this:
@app.route('/list_files', methods=['GET'])
def list_local_files():
    try:
        files = [f for f in os.listdir(ONE_DRIVE_FOLDER) if f.lower().endswith('.xlsx')]
        return jsonify({
            'status': 'success',
            'files': files,
            'folder': ONE_DRIVE_FOLDER  # For debugging
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'folder': ONE_DRIVE_FOLDER  # To verify the path is correct
        }), 500




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

@app.route('/upload_from_link', methods=['POST'])
def upload_from_link():
    data = request.json
    file_url = data.get('file_url')  # This should be a OneDrive link ending with ?download=1

    if not file_url or not file_url.startswith("http"):
        return jsonify({'error': 'Invalid or missing file URL'}), 400

    try:
        response = requests.get(file_url)
        response.raise_for_status()
        xls = pd.ExcelFile(BytesIO(response.content))

        # Example: extract sheet names and return them
        sheet_names = xls.sheet_names
        return jsonify({
            'sheet_names': sheet_names,
            'message': 'File downloaded and processed successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)


