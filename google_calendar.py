import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]


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
            "private": {
                "blackboard_id": assignment.id
            }
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return created_event


def find_assignment_event(service, assignment_id):
    response = service.events().list(
        calendarId="primary",
        privateExtendedProperty=f"blackboard_id={assignment_id}",
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
            "private": {
                "blackboard_id": assignment.id
            }
        },
    }

    updated_event = service.events().update(
        calendarId="primary",
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


if __name__ == "__main__":
    service = get_calendar_service()
    print("Connected to Google Calendar!")