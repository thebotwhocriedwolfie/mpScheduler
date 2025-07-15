import pandas as pd
from collections import defaultdict

#loading data
def load_data(file_path):
    """Load data from Excel file into DataFrames"""
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
#optimised teacher allocation 
def run_teacher_assignment(file_path):
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
            print(f" ERROR: Could not assign Subject {subject_id} for Class {class_id}")

    # Generate output
    output_df = pd.DataFrame(assignments)
    output_df.to_csv("Allocations.csv", index=False)
    
    # Print some stats
    used_teachers = len(set(output_df['TeacherId']))
    total_teachers = len(teacher_df)
    print(f"\nOptimization Results:")
    print(f"Used {used_teachers} out of {total_teachers} available teachers")
    print(f"Utilization rate: {used_teachers/total_teachers:.1%}")
    
    return output_df
