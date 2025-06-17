

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

def get_day(timeslot):
    #supporting function to get day from timeslot - since th is a special case
    return timeslot[:1] if not timeslot.startswith('th') else 'th'

#Main function
def generate_schedule(file_path): #use file path as an argument
    # Load data
    data = load_data(file_path)
    
    # Extract all dataFrames
    class_df = data['class_df']
    teacher_df = data['teacher_df']
    subject_df = data['subject_df']
    room_df = data['room_df']
    timeslot_df = data['timeslot_df']
    classSubject_df = data['classSubject_df']
    teacherSubject_df = data['teacherSubject_df']
    
    #Teacher definitions
    teacher_hours = {teacher_id: 0 for teacher_id in teacherSubject_df['TeacherId'].unique()}
    
    # Define timeslot columns in roomdf
    timeslot_columns = [col for col in room_df.columns if col.startswith(('m', 't', 'w', 'th', 'f'))]
    
    #Initialize class and teacher schedules
    class_schedule = pd.DataFrame(columns=['ClassId'] + timeslot_columns)
    teacher_schedule = pd.DataFrame(columns=['TeacherId'] + timeslot_columns)

    # Defining class schedule - ensures no repeated classes in the same slot
    for class_id in class_df['ClassId']: 
        row = {'ClassId': class_id}
        row.update({col: 'free' for col in timeslot_columns})
        class_schedule = pd.concat([class_schedule, pd.DataFrame([row])], ignore_index=True)
        
    # Defining teacher schedule 
    for teacher_id in teacher_df['TeacherId']:# loop 
        row = {'TeacherId': teacher_id}
        row.update({col: 'free' for col in timeslot_columns})
        teacher_schedule = pd.concat([teacher_schedule, pd.DataFrame([row])], ignore_index=True)
    
    # Dictionaries for tracking
    class_subject_room = {}
    daily_subject_hours = defaultdict(int)
    error_messages = []
    lunchHour = [str(slot) for slot in timeslot_df['SlotID'] if str(slot).endswith(('4', '5'))]
    class_lunch_time = {}
    
    # Main scheduling loop
    results = []
    for class_id in class_df['ClassId']: #loop through each class - scheduler prioritises class 
        class_subjects = classSubject_df[classSubject_df['ClassId'] == class_id]['SubjectId']
        
        for subject_id in class_subjects:#subjects for specified class
            error_messages = set()
            
            filtered = subject_df[subject_df['SubjectId'] == subject_id]
            if filtered.empty: #error handling in case of no subject match
                results.append(f"Error: SubjectId {subject_id} not found in subject_df!")
                continue
            
            subject_info = filtered.iloc[0]
            required_hours = subject_info['TotalWeeklyHours']
            daily_hours_limit = subject_info['Dailyhours']
            session_duration = daily_hours_limit
            hours_count = 0
            
            available_teachers = teacherSubject_df[ #checks for teachers who teaches that subject
                teacherSubject_df['SubjectId'] == subject_id
            ]['TeacherId'].unique() 
            
            while hours_count < required_hours: # keep scheduling until reached max subject hours 
                scheduled_today = False
                
                for timeslot in timeslot_columns: #loop through timeslots 
                    current_day = get_day(timeslot)
                    day_key = (class_id, subject_id, current_day) # Group as a key to check for repeated lessons on same day
                    
                    if daily_subject_hours[day_key] >= daily_hours_limit: #check if subject hours are exceeded in that day
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
                    
                    # Check room availability
                    available_rooms = room_df[
                        (room_df[required_slots] == "free").all(axis=1)
                    ]
                    if available_rooms.empty:
                        error_messages.add(f"No available rooms for Subject {subject_id} in Class {class_id}")
                        continue
                    
                    # Find available teacher
                    found_teacher = None
                    for teacher_id in available_teachers:
                        if teacher_hours[teacher_id] + current_session_duration > 12:
                            continue
                        
                        teacher_idx = teacher_schedule[teacher_schedule['TeacherId'] == teacher_id].index[0]
                        teacher_free = all(
                            teacher_schedule.at[teacher_idx, slot] == "free"
                            for slot in required_slots
                        )
                        
                        if teacher_free: #loop till a teacher is found
                            found_teacher = teacher_id #define available teacher as found
                            break #break when found
                    
                    if not found_teacher: #error message if no teacher
                        error_messages.add(f"No available Teachers for Subject {subject_id} in Class {class_id}")
                    
                    if found_teacher:
                        room_id = available_rooms.iloc[0]['RoomID'] #find room
                        
                        # Update schedules
                        room_df.loc[room_df['RoomID'] == room_id, required_slots] = f"Class {class_id}, Subject {subject_id}"
                        class_schedule.loc[class_schedule['ClassId'] == class_id, required_slots] = f"Subject {subject_id}"
                        teacher_schedule.loc[
                            teacher_schedule['TeacherId'] == found_teacher,
                            required_slots
                        ] = f"Class {class_id}, Subject {subject_id}"
                        
                        #Update counters
                        teacher_hours[found_teacher] += current_session_duration
                        hours_count += current_session_duration
                        daily_subject_hours[day_key] += current_session_duration
                        class_subject_room[(class_id, subject_id)] = room_id
                        
                        #Add to results
                        message = (
                            f"Booked: Class {class_id}, Subject {subject_id} with Teacher {found_teacher} "
                            f"in Room {room_id} at {timeslot} for {current_session_duration} hours"
                        )# show this message when scheduled successfully
                        print(message)
                        results.append(message)  # Store for printing later on
                        scheduled_today = True
                        break
                
                if not scheduled_today:# Print specific error messages on why it cant schedule
                    results.append(
                        f"Error: Could not schedule Class {class_id}, Subject {subject_id}. "
                        f"Remaining hours: {required_hours - hours_count}. "
                        f"Reason: {', '.join(error_messages) if error_messages else 'Unknown reason'}"
                    )
                    break
    
    return {
        'schedule': results, #return results
    }






