# StudySync

StudySync is a Python application that automatically synchronizes university Blackboard assignment deadlines with a dedicated Google Calendar.

It reads the assignment due dates published by Blackboard's iCalendar (ICS) feed, maps each assignment to a course, and mirrors it into a Google Calendar reserved for coursework. The synchronization is idempotent: it can run repeatedly without creating duplicate events, and it only writes to the calendar when something has actually changed. On macOS the sync runs unattended once per hour through a `launchd` agent.

## Key Features

- **Blackboard iCalendar/ICS parsing** — fetches the Blackboard calendar feed over HTTP and extracts gradable items with the `icalendar` library.
- **Google Calendar synchronization** — creates and updates assignment events through the Google Calendar API.
- **OAuth 2.0 authentication** — authorizes against Google with the installed-app flow and caches the resulting token locally, refreshing it automatically as it expires.
- **Dedicated StudySync calendar** — all events are written to a separate Google Calendar rather than the user's primary calendar, so coursework stays isolated and can be toggled or shared on its own.
- **Persistent Blackboard assignment IDs** — each event carries its Blackboard ID in a Google Calendar *shared* extended property, giving every assignment a stable identity independent of the event's own Google-assigned ID.
- **Duplicate prevention** — before creating anything, StudySync queries the calendar for an existing event with the same Blackboard ID.
- **Assignment change detection** — an existing event is rewritten only when its title, course description, start time, or end time no longer matches the feed. Otherwise it is skipped.
- **Time-aware orphan detection** — reports managed future events that no longer appear in the feed, while deliberately ignoring past events.
- **Preservation of historical assignments** — completed and past-due events are never flagged or removed, so the calendar keeps a record of the term.
- **Automated hourly synchronization on macOS** — a `launchd` LaunchAgent runs the sync every hour in the background.

Orphan detection is **report-only**. StudySync never deletes a calendar event; it prints what looks stale and leaves the decision to the user.

## Architecture

```
Blackboard ICS Feed
       |
       v
StudySync Python Application
       |
       +--> Parse assignments
       |
       +--> Compare persistent Blackboard IDs
       |
       +--> Create / Update / Skip
       |
       v
Google Calendar API
       |
       v
Dedicated StudySync Calendar
```

## Synchronization Strategy

The core problem is deciding what a given assignment in the feed means for the calendar. StudySync resolves this with a persistent identity rather than by matching on titles or dates, both of which change.

**Identity.** When an event is created, the Blackboard assignment ID is stored in the event's `extendedProperties.shared.blackboard_id` field. The Google Calendar API can query directly on that property, so StudySync can ask "does an event for this assignment already exist?" without scanning the whole calendar.

**Create, update, or skip.** For each assignment in the feed, StudySync looks up the Blackboard ID. If no event exists, it creates one. If an event exists but its title, description, start, or end differs from the feed, it updates it. If everything matches, it skips the event and makes no API write at all. This is what keeps hourly runs cheap and non-destructive.

**Why missing assignments are not deletions.** The Blackboard feed lists *upcoming* work only. Once an assignment's due date passes, it simply drops out of the feed. A naive synchronizer would interpret every past assignment as "deleted upstream" and remove a full semester of history. StudySync treats absence from the feed as meaningful only for events that are still in the future, since those are the ones the feed would still be reporting if they existed. Any managed event whose start time is already in the past is skipped by orphan detection entirely.

## Tech Stack

| Component | Purpose |
|---|---|
| Python | Application language |
| Google Calendar API | Event creation, lookup, and updates |
| OAuth 2.0 | Google authorization and token refresh |
| iCalendar / `icalendar` | Parsing the Blackboard ICS feed |
| `requests` | Fetching the feed over HTTP |
| `python-dotenv` | Loading configuration from `.env` |
| Git | Version control |
| macOS `launchd` | Hourly scheduled execution |

## Project Structure

```
StudySync/
├── main.py                       # Entry point: fetch, sync, report orphans
├── blackboard.py                 # Fetches and parses the Blackboard ICS feed
├── courses.py                    # Maps assignment titles to course codes and names
├── models.py                     # Assignment dataclass
├── google_calendar.py            # OAuth, event create/update/lookup, orphan detection
├── requirements.txt              # Pinned dependencies
└── .gitignore                    # Excludes credentials, tokens, logs, and local scheduler files
```

## Setup

**1. Create a virtual environment.** Create a Python virtual environment inside the project directory and activate it, so dependencies stay isolated from the system interpreter.

**2. Install dependencies.** Install the pinned packages from `requirements.txt`.

**3. Configure Google OAuth credentials.** In the Google Cloud console, create a project, enable the Google Calendar API, and configure an OAuth consent screen. Create OAuth client credentials of type *Desktop app* and download the client secret file as `credentials.json` in the project root. On the first run, StudySync opens a browser for consent and writes the resulting token to `token.json`. Both files are gitignored and must never be committed.

**4. Create the dedicated calendar.** Create a Google Calendar to receive the assignments — `google_calendar.py` includes a `get_or_create_studysync_calendar` helper that finds a calendar named `StudySync` or creates it. Copy the resulting calendar ID from the calendar's settings.

**5. Configure `.env`.** Create a `.env` file in the project root with the feed URL and calendar ID:

```
BLACKBOARD_ICS_URL=<your_blackboard_calendar_feed>
STUDYSYNC_CALENDAR_ID=<your_google_calendar_id>
```

Both values are required; the application raises a clear error at startup if either is missing.

**6. Run the sync.** Execute `main.py` with the virtual environment's interpreter. Each run prints one line per assignment indicating whether it was created, updated, or skipped, followed by an orphan report.

## Automation

On macOS, synchronization is automated with a user LaunchAgent installed in `~/Library/LaunchAgents/`. The agent is configured with `StartInterval` set to `3600`, so the sync runs once per hour in the background.

Two details matter for the agent to work correctly:

- It invokes the **virtual environment's** Python interpreter directly, since the agent does not inherit an activated shell environment.
- It sets `WorkingDirectory` to the project directory, because `.env`, `token.json`, and `credentials.json` are all resolved as relative paths.

Standard output and standard error are redirected into a gitignored `logs/` directory. The plist itself is gitignored as well: it necessarily contains absolute paths, which makes it specific to one machine.

## Technical Challenges

**Blackboard REST API access was not available.** The original design called for Blackboard's REST API, which exposes rich assignment metadata. Using it requires registering a developer application that a university Blackboard administrator must then approve and install on the institution's instance — a process outside a student's control. After building and testing the OAuth flow against the institutional endpoint, the project was redesigned around the Blackboard ICS feed, which is available to any student directly. The tradeoff is less metadata: the feed provides titles and due dates but no course association, which is why `courses.py` maps assignments to courses by title pattern.

**The feed only describes upcoming work.** Because past assignments disappear from the ICS feed, "present on the calendar but absent from the feed" is ambiguous — it means either *deleted upstream* or *already past due*. Treating both cases the same way would have wiped out the semester's history. Orphan detection therefore compares each event's start time against the current time and considers only future events, which is the subset where absence from the feed is genuinely informative.

**Synchronization needed a persistent event identity.** Matching events by title or due date is unreliable: instructors rename assignments and move deadlines, and either change would cause a rename to be seen as a new assignment and produce a duplicate. Storing the Blackboard assignment ID on the event gives each assignment a stable key, which is what makes the sync idempotent and lets an hourly job run safely forever.

**Extended properties had to survive a calendar migration.** Assignment IDs were first stored in *private* extended properties. When the existing events were migrated from the primary calendar to the dedicated StudySync calendar, the Google Calendar API's `move` operation was found to silently drop private extended properties — which would have severed every event from its Blackboard ID and caused the next sync to recreate all of them as duplicates. Switching to *shared* extended properties preserved the IDs through the move, and the migration was carried out with a one-event-at-a-time script that re-fetched and verified each event after moving it.

## Future Improvements

These are planned ideas, not current functionality:

- **Cross-platform scheduling** — a scheduling path for Linux and Windows, since automation is currently macOS-only via `launchd`.
- **Improved course metadata** — replacing the title-pattern course mapping with something more robust and less manual.
- **Notifications** — alerts summarizing what changed after a sync, and reminders for approaching deadlines.
- **Optional study-planning / AI features** — suggesting study blocks around existing commitments based on upcoming workload.

## License

Released under the MIT License. See [LICENSE](LICENSE).
