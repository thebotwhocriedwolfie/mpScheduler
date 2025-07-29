import pandas as pd
import json
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

#function to load teacher preferences.json
def load_teacher_prefs(json_path):
    try:
        with open(json_path) as f:
            prefs = json.load(f)
            # Convert list to dict if needed
            if isinstance(prefs, list):
                print("Warning: Converted list preferences to dict")
                return {pref['TeacherId']: pref for pref in prefs}  # Adjust key as needed
            return prefs or {}  # Ensure empty dict if file is empty
    except Exception as e:
        print(f"Error loading preferences: {e}")
        return {}  # Always return a dict

def get_day(timeslot):
    #Supporting function to get day from timeslot
    return timeslot[:1] if not timeslot.startswith('th') else 'th'

# Main function to generate the schedule
def generate_schedule(file_path, assignment_csv="Allocations.csv", teacher_prefs=None):
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

    # Teacher-class-subject allocation
    teacherClassSubject_df = pd.read_csv(assignment_csv)

    if teacher_prefs is None:
        teacher_prefs = load_teacher_prefs("preferences.json")

    print("\n=== LOADED TEACHER PREFERENCES ===")  # Debug line
    print(f"Type: {type(teacher_prefs)}")  # Should be dict
    print(f"Contents: {teacher_prefs}")  # Show actual data

    # Teacher definitions
    teacher_hours = {teacher_id: 0 for teacher_id in teacherSubject_df['TeacherId'].unique()}

    # Define timeslot columns in room_df
    timeslot_columns = [col for col in room_df.columns if col.startswith(('m', 't', 'w', 'th', 'f'))]

    # Initialize class and teacher schedules
    class_schedule = pd.DataFrame(columns=['ClassId'] + timeslot_columns)
    teacher_schedule = pd.DataFrame(columns=['TeacherId'] + timeslot_columns)

    for class_id in class_df['ClassId']:
        row = {'ClassId': class_id}
        row.update({col: 'free' for col in timeslot_columns})
        class_schedule = pd.concat([class_schedule, pd.DataFrame([row])], ignore_index=True)

    for teacher_id in teacher_df['TeacherId']:
        row = {'TeacherId': teacher_id}
        row.update({col: 'free' for col in timeslot_columns})
        teacher_schedule = pd.concat([teacher_schedule, pd.DataFrame([row])], ignore_index=True)

    # Tracking dictionaries
    class_subject_room = {}
    daily_subject_hours = defaultdict(int)
    lunchHour = [str(slot) for slot in timeslot_df['SlotID'] if str(slot).endswith(('4', '5'))]
    class_lunch_time = {}

    # Metrics tracking
    used_rooms = set()
    total_rooms = len(room_df)
    preference_violations = 0
    total_attempts = 0

    results = []

    for class_id in class_df['ClassId']:
        class_subjects = classSubject_df[classSubject_df['ClassId'] == class_id]['SubjectId']

        for subject_id in class_subjects:
            filtered = subject_df[subject_df['SubjectId'] == subject_id]
            if filtered.empty:
                results.append(f"Error: SubjectId {subject_id} not found in subject_df!")
                continue

            subject_info = filtered.iloc[0]
            required_hours = subject_info['TotalWeeklyHours']
            daily_hours_limit = subject_info['Dailyhours']
            session_duration = daily_hours_limit
            hours_count = 0

            assigned_teacher = teacherClassSubject_df[
                (teacherClassSubject_df['ClassId'] == class_id) &
                (teacherClassSubject_df['SubjectId'] == subject_id)
            ]

            if assigned_teacher.empty:
                results.append(f"Error: No teacher assigned for Class {class_id}, Subject {subject_id}")
                continue

            assigned_teacher_id = assigned_teacher['TeacherId'].values[0]

            # Track consecutive failures to prevent infinite loops
            consecutive_failures = 0
            max_failures = 10  # Prevent infinite loops

            while hours_count < required_hours and consecutive_failures < max_failures:
                scheduled_this_attempt = False
                error_messages = set()  # Reset for each scheduling attempt

                for timeslot in timeslot_columns:
                    current_day = get_day(timeslot)
                    day_key = (class_id, subject_id, current_day)

                    if daily_subject_hours[day_key] >= daily_hours_limit:
                        error_messages.add(f"Daily limit reached for {current_day}")
                        continue

                    remaining_daily_hours = daily_hours_limit - daily_subject_hours[day_key]
                    current_session_duration = min(session_duration, remaining_daily_hours)

                    current_idx = timeslot_columns.index(timeslot)
                    end_idx = current_idx + current_session_duration
                    if end_idx > len(timeslot_columns) or current_day != get_day(timeslot_columns[end_idx - 1]):
                        error_messages.add(f"Not enough consecutive slots at {timeslot}")
                        continue

                    required_slots = timeslot_columns[current_idx:end_idx]

                    # 1. Lunch hour logic
                    if timeslot in lunchHour and class_id not in class_lunch_time:
                        prev_slot_idx = timeslot_columns.index(timeslot) - 1
                        prev_slot = timeslot_columns[prev_slot_idx] if prev_slot_idx >= 0 else None

                        if class_id in class_lunch_time:
                            if class_lunch_time[class_id] == prev_slot:
                                pass
                            elif class_lunch_time[class_id][-1] == "5" and timeslot[-1] == "4":
                                error_messages.add("Lunch time conflict")
                                continue
                            else:
                                error_messages.add("Lunch time conflict")
                                continue
                        else:
                            if prev_slot and prev_slot[-1] == "3":
                                class_lunch_time[class_id] = timeslot
                                error_messages.add("Lunch time assigned")
                                continue
                            elif timeslot[-1] in ["4", "5"]:
                                class_lunch_time[class_id] = timeslot
                                error_messages.add("Lunch time assigned")
                                continue

                    # 2. Check teacher preferences
                    if assigned_teacher_id in teacher_prefs:
                        pref = teacher_prefs[assigned_teacher_id]

                        if pref.get('full_day', False):
                            preference_violations += 1
                            error_messages.add("Teacher unavailable (full day)")
                            continue

                        if current_day.lower() in [d.lower() for d in pref.get('unavailable_days', [])]:
                            preference_violations += 1
                            error_messages.add(f"Teacher unavailable on {current_day}")
                            continue

                        unavailable_slots = pref.get('unavailable_slots', [])
                        if any(slot.lower().replace(" ", "") in [s.lower().replace(" ", "") for s in unavailable_slots] for slot in required_slots):
                            preference_violations += 1
                            error_messages.add("Teacher unavailable (slot preference)")
                            continue

                    # 3. Check class availability
                    class_free = all(
                        class_schedule.loc[class_schedule['ClassId'] == class_id, slot].iloc[0] == "free"
                        for slot in required_slots
                    )
                    if not class_free:
                        error_messages.add("Class already scheduled")
                        continue

                    # 4. Check teacher availability
                    teacher_idx = teacher_schedule[teacher_schedule['TeacherId'] == assigned_teacher_id].index[0]
                    teacher_free = all(
                        teacher_schedule.at[teacher_idx, slot] == "free"
                        for slot in required_slots
                    )
                    if not teacher_free:
                        error_messages.add(f"Teacher {assigned_teacher_id} already scheduled")
                        continue
                        
                    if teacher_hours[assigned_teacher_id] + current_session_duration > 12:
                        error_messages.add(f"Teacher {assigned_teacher_id} exceeds max hours")
                        continue

                    # 5. Check room availability
                    available_rooms = room_df[(room_df[required_slots] == "free").all(axis=1)]
                    if available_rooms.empty:
                        error_messages.add("No available rooms")
                        continue

                    # ✅ ALL CHECKS PASSED - MAKE THE BOOKING
                    room_id = available_rooms.iloc[0]['RoomID']

                    # Update all schedules
                    room_df.loc[room_df['RoomID'] == room_id, required_slots] = f"Class {class_id}, Subject {subject_id}"
                    class_schedule.loc[class_schedule['ClassId'] == class_id, required_slots] = f"Subject {subject_id}"
                    teacher_schedule.loc[teacher_idx, required_slots] = f"Class {class_id}, Subject {subject_id}"

                    # Update tracking
                    teacher_hours[assigned_teacher_id] += current_session_duration
                    hours_count += current_session_duration
                    daily_subject_hours[day_key] += current_session_duration
                    class_subject_room[(class_id, subject_id)] = room_id
                    used_rooms.add(room_id)
                    total_attempts += 1

                    message = (
                        f"Booked: Class {class_id}, Subject {subject_id} with Teacher {assigned_teacher_id} "
                        f"in Room {room_id} at {timeslot} for {current_session_duration} hours"
                    )
                    print(message)
                    results.append(message)
                    
                    scheduled_this_attempt = True
                    consecutive_failures = 0  # Reset failure counter
                    break  # Break out of timeslot loop, continue with while loop

                # Check if we made progress this round
                if not scheduled_this_attempt:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        results.append(
                            f"Error: Could not schedule Class {class_id}, Subject {subject_id}. "
                            f"Hours count: {hours_count}/{required_hours}. "
                            f"Reason: {', '.join(error_messages) if error_messages else 'No available slots found'}"
                        )
                        break  # Exit while loop for this subject

    # Final metrics calculation
    total_preference_checks = sum(
        1 for _ in teacherClassSubject_df.itertuples() 
        if _.TeacherId in teacher_prefs
    )
    preference_score = (
        100 - (preference_violations / total_preference_checks * 100) 
        if total_preference_checks > 0 
        else 100
    )

    successful_bookings = len([r for r in results if r.startswith("Booked:")])
    failed_bookings = len([r for r in results if r.startswith("Error:")])

    print("\n=== SCHEDULING SUMMARY ===")
    print(f"• Rooms Used: {len(used_rooms)}/{total_rooms}")
    print(f"• Teacher Preferences Honored: {preference_score:.1f}%")
    print(f"• Successful Bookings: {successful_bookings}")
    print(f"• Failed Bookings: {failed_bookings}")
                    
    return {
        'schedule': results,
        'metrics': {
            'rooms_utilized': f"{len(used_rooms)}/{total_rooms}",
            'preference_score': f"{preference_score:.1f}%",
            'successful_assignments': successful_bookings,
            'failed_assignments': failed_bookings
        }
    }
