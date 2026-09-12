COURSES = {
    "CSCE_31903_001": "Programming Paradigms",
    "CSCE_36103_001": "Operating Systems",
    "INEG_33103_901": "Engineering Probability & Statistics",
    "MATH_30803_005": "Linear Algebra"
}

ASSIGNMENT_RULES = {
    # Operating Systems
    "Processes, Threads, and Resources": "CSCE_36103_001",
    "Bits, Bytes, Words": "CSCE_36103_001",
    "Scheduling": "CSCE_36103_001",

    # Linear Algebra
    "Homework Section": "MATH_30803_005",

    # Engineering Probability & Statistics
    "Week": "INEG_33103_901",
    "Assignment": "INEG_33103_901",

    # Programming Paradigms
    "Project #": "CSCE_31903_001",
    "Quiz-": "CSCE_31903_001",
    "Mid Term": "CSCE_31903_001",
    "Final Exam": "CSCE_31903_001"
}

def get_course_for_assignment(title):
    for pattern, course_code in ASSIGNMENT_RULES.items():
        if pattern in title:
            return course_code

    return None