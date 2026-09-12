import os
import requests
from dotenv import load_dotenv
from icalendar import Calendar
from datetime import datetime
from models import Assignment
from courses import get_course_for_assignment, COURSES


load_dotenv()
BLACKBOARD_ICS_URL = os.getenv("BLACKBOARD_ICS_URL")

def load_calendar():
    if not BLACKBOARD_ICS_URL:
        raise ValueError("BLACKBOARD_ICS_URL is missing from .env")

    response = requests.get(BLACKBOARD_ICS_URL, timeout=10)
    response.raise_for_status()

    calendar = Calendar.from_ical(response.content)

    return calendar

def get_assignments():
    calendar = load_calendar()
    now = datetime.now().astimezone()
    assignments = []

    for component in calendar.walk():
        if component.name == "VEVENT":
           uid = str(component.get("uid"))
           assignment_id = uid.split("GradableItem-")[-1]

           if "GradableItem" in uid:
                title = component.get("summary")
                due_date = component.get("dtstart").dt

                if due_date >= now:
                    course_code = get_course_for_assignment(str(title))

                    assignment = Assignment(
                        id=assignment_id,
                        title=str(title),
                        due_date=due_date,
                        course_code=course_code,
                        course_name=COURSES.get(course_code)
                    )

                    assignments.append(assignment)
    
    assignments.sort(key=lambda assignment: assignment.due_date)
    
    return assignments