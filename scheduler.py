import pandas as pd
from collections import defaultdict

#function to load data
def load_data(file_path):
    """Load data from Excel file into DataFrames"""
    xls = pd.ExcelFile(file_path)
    
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

def get_day(timeslot):
    #Supporting function to get day from timeslot
    return timeslot[:1] if not timeslot.startswith('th') else 'th'

#Main function to generate the schedule
def generate_schedule(file_path, assignment_csv): #use selected dataset and teacher/class allocation csv
    # Load data
    data = load_data(file_path)
    
    #Extract all dataFrames
    class_df = data['class_df']
    teacher_df = data['teacher_df']
    subject_df = data['subject_df']
    room_df = data['room_df']
    timeslot_df = data['timeslot_df']
    classSubject_df = data['classSubject_df']
    teacherSubject_df = data['teacherSubject_df']
    
    #teacher class subject allocation datafile
    teacherClassSubject_df = pd.read_csv(assignment_csv) 
    
    #Teacher definitions
    teacher_hours = {teacher_id: 0 for teacher_id in teacherSubject_df['TeacherId'].unique()}
    
    # Define timeslot columns in roomdf
    timeslot_columns = [col for col in room_df.columns if col.startswith(('m', 't', 'w', 'th', 'f'))]
    
    # Initialize class and teacher schedules
    class_schedule = pd.DataFrame(columns=['ClassId'] + timeslot_columns)
    teacher_schedule = pd.DataFrame(columns=['TeacherId'] + timeslot_columns)

    # Defining class schedule
    for class_id in class_df['ClassId']: 
        row = {'ClassId': class_id}
        row.update({col: 'free' for col in timeslot_columns})
        class_schedule = pd.concat([class_schedule, pd.DataFrame([row])], ignore_index=True)
        
    # Defining teacher schedule 
    for teacher_id in teacher_df['TeacherId']:
        row = {'TeacherId': teacher_id}
        row.update({col: 'free' for col in timeslot_columns})
        teacher_schedule = pd.concat([teacher_schedule, pd.DataFrame([row])], ignore_index=True)
    
    #Dictionaries for tracking
    class_subject_room = {}
    daily_subject_hours = defaultdict(int)
    error_messages = []
    lunchHour = [str(slot) for slot in timeslot_df['SlotID'] if str(slot).endswith(('4', '5'))]
    class_lunch_time = {}
    
    #Main scheduling loop
    results = []
    for class_id in class_df['ClassId']:
        class_subjects = classSubject_df[classSubject_df['ClassId'] == class_id]['SubjectId']
        
        for subject_id in class_subjects:
            error_messages = set()
            
            filtered = subject_df[subject_df['SubjectId'] == subject_id]
            if filtered.empty:
                results.append(f"Error: SubjectId {subject_id} not found in subject_df!")
                continue
            
            subject_info = filtered.iloc[0]
            required_hours = subject_info['TotalWeeklyHours']
            daily_hours_limit = subject_info['Dailyhours']
            session_duration = daily_hours_limit
            hours_count = 0
            
            #Assign teachers from the assignment CSV
            assigned_teacher = teacherClassSubject_df[
                (teacherClassSubject_df['ClassId'] == class_id) & 
                (teacherClassSubject_df['SubjectId'] == subject_id)
            ] 
            
            if assigned_teacher.empty:
                results.append(f"Error: No teacher assigned for Class {class_id}, Subject {subject_id}")
                continue
                
            assigned_teacher_id = assigned_teacher['TeacherId'].values[0] #whats this for ?
            
            while hours_count < required_hours:
                scheduled_today = False
                
                for timeslot in timeslot_columns:
                    current_day = get_day(timeslot)
                    day_key = (class_id, subject_id, current_day)
                    
                    if daily_subject_hours[day_key] >= daily_hours_limit:
                        continue
                    
                    remaining_daily_hours = daily_hours_limit - daily_subject_hours[day_key]
                    current_session_duration = min(session_duration, remaining_daily_hours)
                    
                    current_idx = timeslot_columns.index(timeslot)
                    end_idx = current_idx + current_session_duration
                    if end_idx > len(timeslot_columns) or current_day != get_day(timeslot_columns[end_idx - 1]):
                        continue
                    
                    required_slots = timeslot_columns[current_idx:end_idx]
                    
                    # Lunch hour logic
                    if timeslot in lunchHour and class_id not in class_lunch_time:
                        prev_slot = timeslot_columns[timeslot_columns.index(timeslot) - 1] if timeslot_columns.index(timeslot) > 0 else None
                        
                        if class_id in class_lunch_time:
                            if class_lunch_time[class_id] == prev_slot:
                                pass
                            elif class_lunch_time[class_id][-1] == "5" and timeslot[-1] == "4":
                                continue
                            else:
                                continue
                        else:
                            if prev_slot and prev_slot[-1] == "3":
                                class_lunch_time[class_id] = timeslot
                                continue
                            elif timeslot[-1] == "4":
                                class_lunch_time[class_id] = timeslot
                            elif timeslot[-1] == "5":
                                class_lunch_time[class_id] = timeslot
                            continue
                    
                    # Check class availability
                    class_free = all(
                        class_schedule.loc[class_schedule['ClassId'] == class_id, slot].iloc[0] == "free"
                        for slot in required_slots
                    )
                    if not class_free:
                        continue
                    
                    # Check teacher availability
                    teacher_idx = teacher_schedule[teacher_schedule['TeacherId'] == assigned_teacher_id].index[0]
                    teacher_free = all(
                        teacher_schedule.at[teacher_idx, slot] == "free"
                        for slot in required_slots
                    )
                    if not teacher_free or teacher_hours[assigned_teacher_id] + current_session_duration > 12:
                        error_messages.add(f"Teacher {assigned_teacher_id} unavailable")
                        continue
                    
                    # Check room availability
                    available_rooms = room_df[
                        (room_df[required_slots] == "free").all(axis=1)
                    ]
                    if available_rooms.empty:
                        error_messages.add("No available rooms")
                        continue
                    
                    # Assign room
                    room_id = available_rooms.iloc[0]['RoomID']
                    
                    # Update schedules
                    room_df.loc[room_df['RoomID'] == room_id, required_slots] = f"Class {class_id}, Subject {subject_id}"
                    class_schedule.loc[class_schedule['ClassId'] == class_id, required_slots] = f"Subject {subject_id}"
                    teacher_schedule.loc[teacher_idx, required_slots] = f"Class {class_id}, Subject {subject_id}"
                    
                    # Update counts
                    teacher_hours[assigned_teacher_id] += current_session_duration
                    hours_count += current_session_duration
                    daily_subject_hours[day_key] += current_session_duration
                    class_subject_room[(class_id, subject_id)] = room_id
                    
                    # Add to results
                    message = (
                        f"Booked: Class {class_id}, Subject {subject_id} with Teacher {assigned_teacher_id} "
                        f"in Room {room_id} at {timeslot} for {current_session_duration} hours"
                    )
                    print(message)
                    results.append(message)
                    scheduled_today = True
                    break
                
                if not scheduled_today:
                    results.append(
                        f"Error: Could not schedule Class {class_id}, Subject {subject_id}. "
                        f"Remaining hours: {required_hours - hours_count}. "
                        f"Reason: {', '.join(error_messages) if error_messages else 'Unknown reason'}"
                    )
                    break
    
    return {
        'schedule': results,
        'class_schedule': class_schedule,
        'teacher_schedule': teacher_schedule,
        'room_schedule': room_df
    }

#testing function 
file_path = "2023_APRIL_SEM.xlsx" 
schedule_result = generate_schedule(file_path,"MP_allocations.csv")

# Print the generated schedule
for entry in schedule_result['schedule']:
    print(entry)
