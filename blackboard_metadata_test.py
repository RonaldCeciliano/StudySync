import requests


TEST_URL = (
    "https://learn.uark.edu/learn/api/v1/calendars/dueDateCalendarItems"
    "?date=2026-08-26T05:00:00.000Z"
    "&date_compare=greaterOrEqual"
    "&includeCount=true"
    "&limit=20"
    "&offset=0"
)


response = requests.get(TEST_URL, timeout=10)

print("Status:", response.status_code)
print()
print(response.text[:1000])