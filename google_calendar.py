import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]

load_dotenv()
STUDYSYNC_CALENDAR_ID = os.getenv("STUDYSYNC_CALENDAR_ID")

if not STUDYSYNC_CALENDAR_ID:
    raise ValueError("STUDYSYNC_CALENDAR_ID is missing from .env")


def get_calendar_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )

            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    return service


def create_assignment_event(service, assignment):
    event = {
        "summary": assignment.title,
        "description": f"Course: {assignment.course_name}",

        "start": {
            "dateTime": assignment.due_date.isoformat(),
        },

        "end": {
            "dateTime": (assignment.due_date + timedelta(minutes=30)).isoformat(),
        },

        "extendedProperties": {
            "shared": {
                "blackboard_id": assignment.id
            }
        },
    }

    created_event = service.events().insert(
        calendarId=STUDYSYNC_CALENDAR_ID,
        body=event
    ).execute()

    return created_event


def find_assignment_event(service, assignment_id):
    response = service.events().list(
        calendarId=STUDYSYNC_CALENDAR_ID,
        sharedExtendedProperty=f"blackboard_id={assignment_id}",
        maxResults=1,
        singleEvents=True
    ).execute()

    events = response.get("items", [])

    if events:
        return events[0]

    return None


def read_event_time(event_time):
    text = event_time.get("dateTime")

    if not text:
        return None

    # Google can end times with "Z", which fromisoformat does not accept.
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def assignment_needs_update(existing_event, assignment):
    if existing_event.get("summary") != assignment.title:
        return True

    if existing_event.get("description") != f"Course: {assignment.course_name}":
        return True

    start = read_event_time(existing_event.get("start", {}))

    if start != assignment.due_date:
        return True

    end = read_event_time(existing_event.get("end", {}))

    if end != assignment.due_date + timedelta(minutes=30):
        return True

    return False


def update_assignment_event(service, existing_event, assignment):
    event = {
        "summary": assignment.title,
        "description": f"Course: {assignment.course_name}",

        "start": {
            "dateTime": assignment.due_date.isoformat(),
        },

        "end": {
            "dateTime": (assignment.due_date + timedelta(minutes=30)).isoformat(),
        },

        "extendedProperties": {
            "shared": {
                "blackboard_id": assignment.id
            }
        },
    }

    updated_event = service.events().update(
        calendarId=STUDYSYNC_CALENDAR_ID,
        eventId=existing_event["id"],
        body=event
    ).execute()

    return updated_event


def sync_assignment(service, assignment):
    existing_event = find_assignment_event(service, assignment.id)

    if not existing_event:
        created_event = create_assignment_event(service, assignment)

        print(f"Created: {assignment.title}")

        return created_event

    if assignment_needs_update(existing_event, assignment):
        updated_event = update_assignment_event(service, existing_event, assignment)

        print(f"Updated: {assignment.title}")

        return updated_event

    print(f"Skipped (already synced): {assignment.title}")

    return existing_event


def sync_assignments(service, assignments):
    for assignment in assignments:
        sync_assignment(service, assignment)


def get_blackboard_id(event):
    # shared properties survive events().move, private ones do not
    shared = event.get("extendedProperties", {}).get("shared", {})

    return shared.get("blackboard_id")


def get_studysync_events(service):
    studysync_events = []
    page_token = None

    while True:
        response = service.events().list(
            calendarId=STUDYSYNC_CALENDAR_ID,
            singleEvents=True,
            maxResults=250,
            pageToken=page_token
        ).execute()

        for event in response.get("items", []):
            # only events StudySync created carry a blackboard_id
            if get_blackboard_id(event):
                studysync_events.append(event)

        page_token = response.get("nextPageToken")

        if not page_token:
            return studysync_events


def find_orphaned_events(service, assignments):
    assignment_ids = set()

    for assignment in assignments:
        assignment_ids.add(assignment.id)

    # the Blackboard feed only lists upcoming work, so a past event is
    # missing from that list for a harmless reason and is never an orphan
    now = datetime.now().astimezone()

    orphaned_events = []

    for event in get_studysync_events(service):
        start = read_event_time(event.get("start", {}))

        if start is None:
            print(f"Skipped orphan check for event with unreadable start time: {event.get('summary')}")
            continue

        if start < now:
            continue

        if get_blackboard_id(event) not in assignment_ids:
            orphaned_events.append(event)

    return orphaned_events


def report_orphaned_events(service, assignments):
    orphaned_events = find_orphaned_events(service, assignments)

    if not orphaned_events:
        print("No orphaned calendar events found.")

        return orphaned_events

    for event in orphaned_events:
        print(f"Orphaned calendar event: {event.get('summary')}")

    return orphaned_events


def find_calendar_by_name(service, calendar_name):
    page_token = None

    while True:
        response = service.calendarList().list(pageToken=page_token).execute()

        for calendar in response.get("items", []):
            if calendar.get("summary") == calendar_name:
                return calendar

        page_token = response.get("nextPageToken")

        if not page_token:
            return None


def get_or_create_studysync_calendar(service):
    # look first so we never end up with two StudySync calendars
    existing_calendar = find_calendar_by_name(service, "StudySync")

    if existing_calendar:
        return existing_calendar["id"]

    created_calendar = service.calendars().insert(
        body={
            "summary": "StudySync",
            "description": "Assignments synced from Blackboard by StudySync.",
        }
    ).execute()

    return created_calendar["id"]


if __name__ == "__main__":
    service = get_calendar_service()
    print("Connected to Google Calendar!")