from flask import Flask, request, jsonify
from scheduler import generate_schedule  #import function from scheduler.py


app = Flask(__name__)

@app.route('/generate_schedule', methods=['POST'])
def api_generate_schedule():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        file_path = f"temp_{file.filename}"
        file.save(file_path)

        #Call the scheduler function (generate_schedule)
        result = generate_schedule(file_path)

        return jsonify(result)  # This returns {'schedule': [...]}
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        import os
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    app.run(debug=True)
