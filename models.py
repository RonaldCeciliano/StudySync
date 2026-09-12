from dataclasses import dataclass
from datetime import datetime

@dataclass
class Assignment:
    id: str
    title: str
    due_date: datetime
    course_code: str | None = None
    course_name: str | None = None
    assignment_type: str | None = None

