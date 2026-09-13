from blackboard import get_assignments
from google_calendar import (
    get_calendar_service,
    sync_assignments,
    report_orphaned_events,
)

assignments = get_assignments()

service = get_calendar_service()

sync_assignments(service, assignments)

report_orphaned_events(service, assignments)
