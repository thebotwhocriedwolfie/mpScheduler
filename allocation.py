import pandas as pd
from collections import defaultdict
from io import BytesIO

def load_data(file_path):
    """Load data from Excel file into DataFrames"""
    if file_path.startswith("http"):
        response = requests.get(file_path)
        response.raise_for_status()
        xls = pd.ExcelFile(BytesIO(response.content))
    else:
        xls = pd.ExcelFile(file_path)
    
    #defining tables
    return {
        'class_df': pd.read_excel(xls, 'Class Table'),
        'teacher_df': pd.read_excel(xls, 'Teacher Table'),
        'subject_df': pd.read_excel(xls, 'Subject Table'),
        'room_df': pd.read_excel(xls, 'Room Table'),
        'timeslot_df': pd.read_excel(xls, 'Timeslot Table'),
        'booking_df': pd.read_excel(xls, 'Booking Table'),
        'classSubject_df': pd.read_excel(xls, 'ClassSubject Table'),
        'teacherSubject_df': pd.read_excel(xls, 'TeacherSubject Table')
    }

def run_teacher_assignment(file_path):
    # Load all data first
    data = load_data(file_path)
    
    class_df = data['class_df']
    teacher_df = data['teacher_df']
    subject_df = data['subject_df']
    classSubject_df = data['classSubject_df']
    qualification_df = data['teacherSubject_df']  # eligibility

    # Initialize tracking dictionaries
    teacher_load = {tid: 0 for tid in teacher_df['TeacherId']}
    teacher_class_count = {tid: 0 for tid in teacher_df['TeacherId']}
    teacher_subject_class_count = {}  # (teacher_id, subject_id): count
    teacher_subjects = {tid: set() for tid in teacher_df['TeacherId']}  # Track subjects per teacher

    assignments = []
    errors = []  # FIXED: Initialize errors list

    # Sort class-subject pairs by subject first (to group same subjects together)
    sorted_class_subjects = classSubject_df.sort_values(['SubjectId', 'ClassId']).iterrows()

    for _, cs_row in sorted_class_subjects:
        class_id = cs_row['ClassId']
        subject_id = cs_row['SubjectId']
        weekly_hours = subject_df.loc[subject_df['SubjectId'] == subject_id, 'TotalWeeklyHours'].values[0]

        # Get eligible teachers and sort them strategically
        eligible_teachers = qualification_df[qualification_df['SubjectId'] == subject_id]['TeacherId'].tolist()
        
        eligible_teachers.sort(key=lambda t: (
            -teacher_subject_class_count.get((t, subject_id), 0),  # Already teaching this subject
            - (20 - teacher_load[t]),  # Most remaining capacity
            len(teacher_subjects[t])  # Fewest subjects taught
        ))

        assigned = False
        for teacher_id in eligible_teachers:
            current_load = teacher_load[teacher_id]
            current_class_count = teacher_class_count[teacher_id]
            current_subject_class = teacher_subject_class_count.get((teacher_id, subject_id), 0)

            if (current_load + weekly_hours <= 20 and
                current_class_count < 3 and
                current_subject_class < 2):

                teacher_load[teacher_id] += weekly_hours
                teacher_class_count[teacher_id] += 1
                teacher_subject_class_count[(teacher_id, subject_id)] = current_subject_class + 1
                teacher_subjects[teacher_id].add(subject_id)

                assignments.append({
                    'TeacherId': teacher_id,
                    'ClassId': class_id,
                    'SubjectId': subject_id
                })
                assigned = True
                break

        if not assigned:
            error_msg = f"Could not assign Subject {subject_id} for Class {class_id}"
            errors.append(error_msg)
            print(f" ERROR: {error_msg}")

    # Generate output
    output_df = pd.DataFrame(assignments)
    
    # Print some stats
    used_teachers = len(set(output_df['TeacherId'])) if len(output_df) > 0 else 0
    total_teachers = len(teacher_df)
    print(f"\nOptimization Results:")
    print(f"Used {used_teachers} out of {total_teachers} available teachers")
    if total_teachers > 0:
        print(f"Utilization rate: {used_teachers/total_teachers:.1%}")
    
    # FIXED: Return both results and errors
    return {
        'assignments_df': output_df,
        'errors': errors,
        'stats': {
            'used_teachers': used_teachers,
            'total_teachers': total_teachers,
            'utilization_rate': used_teachers/total_teachers if total_teachers > 0 else 0
        }
    }

# FIXED: Updated Flask API endpoint
@app.route('/assign_teachers', methods=['POST'])
def api_assign_teachers():
    data = request.json
    file_path = data.get('file_path')
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    try:
        result = run_teacher_assignment(file_path)
        output_df = result['assignments_df']
        errors = result['errors']
        
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
            }), 422  # 422 Unprocessable Entity (not a server error, but a business logic issue)
        
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
                    'errors': errors[:10]  # Show first 10 errors as examples
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
