from blackboard import get_assignments
from google_calendar import get_calendar_service, sync_assignments

assignments = get_assignments()

service = get_calendar_service()

sync_assignments(service, assignments)
