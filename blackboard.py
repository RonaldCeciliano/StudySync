import logging
import os
import requests
from dotenv import load_dotenv
from icalendar import Calendar
from datetime import datetime
from models import Assignment
from courses import get_course_for_assignment, COURSES


load_dotenv()
BLACKBOARD_ICS_URL = os.getenv("BLACKBOARD_ICS_URL")
logger = logging.getLogger(__name__)


def parse_assignment_due_date(component):
    dtstart = component.get("dtstart")
    due_date = getattr(dtstart, "dt", None)

    if dtstart is None:
        reason = "missing DTSTART"
    elif not isinstance(due_date, datetime):
        reason = "DTSTART must include a valid date and time"
    elif due_date.utcoffset() is None:
        reason = "DTSTART has no timezone"
    else:
        return due_date

    logger.warning(
        "Skipping assignment %s (%s): %s",
        component.get("uid"), component.get("summary"), reason,
    )
    return None

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
                due_date = parse_assignment_due_date(component)

                if due_date is None:
                    continue

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
