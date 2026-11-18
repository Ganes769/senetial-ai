# Sentinel AI — Backend API Specification

## 1. Dashboard & Agent Status

These endpoints power the Overview dashboard.

| Method | Endpoint        | What it does                                                                           |
| ------ | --------------- | -------------------------------------------------------------------------------------- |
| GET    | `/overview`     | Returns dashboard statistics, active missions, discoveries, alerts and recent activity |
| GET    | `/agent/status` | Returns the central agent's current status                                             |
| POST   | `/agent/pause`  | Pauses monitoring globally                                                             |
| POST   | `/agent/resume` | Resumes monitoring                                                                     |
| GET    | `/agent/health` | Returns worker health, queue status and last successful execution                      |

Example: `GET /overview`

Response:

```json
{
  "agent_status": "running",
  "active_missions": 5,
  "monitored_sources": 48,
  "discoveries_today": 26,
  "important_alerts": 4,
  "reports_today": 3
}
```

## 2. Mission Management

A mission represents something you want Sentinel to monitor.

Examples:

- Monitor the AI industry.
- Track software engineering opportunities.
- Monitor new AI startups.
- Track new open-source frameworks.

| Method | Endpoint                          | What it does                                |
| ------ | --------------------------------- | ------------------------------------------- |
| POST   | `/missions`                       | Creates a monitoring mission                |
| GET    | `/missions`                       | Lists all missions                          |
| GET    | `/missions/{mission_id}`          | Returns mission details                     |
| PATCH  | `/missions/{mission_id}`          | Updates mission instructions or preferences |
| DELETE | `/missions/{mission_id}`          | Deletes a mission                           |
| POST   | `/missions/{mission_id}/activate` | Activates monitoring                        |
| POST   | `/missions/{mission_id}/pause`    | Pauses an individual mission                |

Example: `POST /missions`

Request:

```json
{
  "name": "AI Industry Intelligence",
  "instruction": "Monitor AI companies, new models, research and agent frameworks.",
  "topics": ["AI agents", "LLMs", "AI research", "Open source"],
  "auto_discover_sources": true,
  "require_source_approval": true,
  "monitoring_interval_minutes": 30
}
```

Response:

```json
{
  "id": "mission_001",
  "name": "AI Industry Intelligence",
  "status": "draft",
  "message": "Mission created successfully"
}
```

## 3. Source Discovery

This module allows Sentinel to discover information sources automatically using the user's mission instructions.

| Method | Endpoint                                        | What it does                                   |
| ------ | ----------------------------------------------- | ---------------------------------------------- |
| POST   | `/missions/{mission_id}/discover`               | Starts the LangGraph source discovery workflow |
| GET    | `/missions/{mission_id}/candidates`             | Lists discovered source candidates             |
| POST   | `/candidates/{candidate_id}/approve`            | Approves a discovered source                   |
| POST   | `/candidates/{candidate_id}/reject`             | Rejects a discovered source                    |
| POST   | `/missions/{mission_id}/candidates/approve-all` | Approves all eligible candidates               |

The discovery workflow:

1. Reads the mission instructions.
2. Extracts topics and search keywords.
3. Generates search queries.
4. Finds public websites, RSS feeds and APIs.
5. Evaluates source relevance.
6. Removes duplicates.
7. Saves candidates.
8. Presents candidates for approval.

Example: `POST /missions/mission_001/discover`

Response:

```json
{
  "run_id": "run_001",
  "status": "queued",
  "message": "Source discovery started"
}
```

## 4. Source Management

This module controls all sources that Sentinel monitors.

| Method | Endpoint                         | What it does                       |
| ------ | -------------------------------- | ---------------------------------- |
| POST   | `/sources`                       | Adds a source manually             |
| GET    | `/sources`                       | Lists monitored sources            |
| GET    | `/sources/{source_id}`           | Gets source details                |
| PATCH  | `/sources/{source_id}`           | Updates source configuration       |
| DELETE | `/sources/{source_id}`           | Removes a source                   |
| POST   | `/sources/{source_id}/test`      | Tests source accessibility         |
| POST   | `/sources/{source_id}/check-now` | Queues an immediate collection job |

Supported source types:

- Website
- RSS
- GitHub
- Public API
- Research publication
- News website

A source can be assigned to multiple missions through a mission-source relationship.

Example: `POST /sources`

```json
{
  "name": "Example AI Blog",
  "url": "https://example.com/blog",
  "type": "website",
  "mission_id": "mission_001"
}
```

## 5. Intelligence Feed & Discoveries

This module powers the Intelligence Feed.

| Method | Endpoint                               | What it does                           |
| ------ | -------------------------------------- | -------------------------------------- |
| GET    | `/discoveries`                         | Lists discoveries across missions      |
| GET    | `/discoveries/{discovery_id}`          | Returns complete discovery details     |
| POST   | `/discoveries/{discovery_id}/bookmark` | Saves a discovery                      |
| DELETE | `/discoveries/{discovery_id}/bookmark` | Removes a bookmark                     |
| POST   | `/discoveries/{discovery_id}/feedback` | Records whether a discovery was useful |
| POST   | `/discoveries/{discovery_id}/read`     | Marks a discovery as read              |

Supported query parameters:

```text
GET /discoveries?importance=high
GET /discoveries?category=technology
GET /discoveries?mission_id=mission_001
GET /discoveries?q=AI+agents
GET /discoveries?limit=20&offset=0
```

Discovery objects should contain:

- Title
- Summary
- What happened
- Why it matters
- Importance
- Relevance score
- Category
- Original source links
- Publication timestamp
- Discovery timestamp
- Investigation status

## 6. Intelligence Reports

This module provides daily briefings and detailed reports.

| Method | Endpoint                                | What it does               |
| ------ | --------------------------------------- | -------------------------- |
| GET    | `/reports`                              | Lists generated reports    |
| GET    | `/reports/{report_id}`                  | Returns complete report    |
| POST   | `/reports/generate`                     | Requests a new report      |
| GET    | `/reports/{report_id}/export?format=md` | Exports report as Markdown |
| DELETE | `/reports/{report_id}`                  | Deletes a report           |

Report generation can be triggered automatically or manually.

Request:

```json
{
  "mission_id": "mission_001",
  "period": "daily"
}
```

The report should include:

- Executive summary
- Important developments
- New discoveries
- Industry trends
- Historical comparisons
- Original source references

## 7. Agent Activity & Execution Runs

This module powers the Live Activity dashboard.

| Method | Endpoint                | What it does                           |
| ------ | ----------------------- | -------------------------------------- |
| GET    | `/activity`             | Returns recent agent activity          |
| GET    | `/runs`                 | Lists agent execution runs             |
| GET    | `/runs/{run_id}`        | Returns execution details              |
| POST   | `/runs/{run_id}/retry`  | Retries a failed execution             |
| POST   | `/runs/{run_id}/cancel` | Requests cancellation of an active run |

Track activities such as:

- Discovering sources
- Fetching information
- Detecting changes
- Investigating findings
- Retrieving memory
- Generating reports
- Sending notifications

## 8. Persistent Memory

This module manages information Sentinel remembers.

| Method | Endpoint              | What it does               |
| ------ | --------------------- | -------------------------- |
| GET    | `/memory`             | Lists stored memories      |
| GET    | `/memory/{memory_id}` | Gets a particular memory   |
| PATCH  | `/memory/{memory_id}` | Updates a memory           |
| DELETE | `/memory/{memory_id}` | Deletes a memory           |
| POST   | `/memory/search`      | Searches historical memory |

Memory categories:

- Personal interests
- User preferences
- Historical discoveries
- Important entities
- Monitoring context
- Previous analysis

Use PostgreSQL for structured memory records and pgvector for semantic retrieval.

## 9. Notifications

| Method | Endpoint                      | What it does                     |
| ------ | ----------------------------- | -------------------------------- |
| GET    | `/notifications`              | Lists notifications              |
| GET    | `/notifications/unread-count` | Returns unread count             |
| POST   | `/notifications/{id}/read`    | Marks a notification as read     |
| POST   | `/notifications/read-all`     | Marks all as read                |
| GET    | `/notifications/preferences`  | Gets notification preferences    |
| PATCH  | `/notifications/preferences`  | Updates notification preferences |

## 10. Connections & Integrations

These are optional future integrations.

| Method | Endpoint                            | What it does               |
| ------ | ----------------------------------- | -------------------------- |
| GET    | `/connections`                      | Lists connected services   |
| POST   | `/connections/{provider}/authorize` | Starts OAuth authorization |
| DELETE | `/connections/{provider}`           | Revokes an integration     |
| GET    | `/connections/{provider}/status`    | Gets connection status     |

Potential integrations:

- GitHub
- Gmail
- Google Calendar
- Other APIs

Use OAuth and minimum permissions. Never store raw account passwords.

## 11. User Settings

| Method | Endpoint          | What it does                  |
| ------ | ----------------- | ----------------------------- |
| GET    | `/settings`       | Retrieves user settings       |
| PATCH  | `/settings`       | Updates preferences           |
| GET    | `/settings/agent` | Retrieves agent configuration |
| PATCH  | `/settings/agent` | Updates agent behaviour       |

## 12. Real-time WebSocket

Endpoint:

`WS /api/v1/ws`

The React frontend connects to this endpoint to receive live events.

Example events:

```json
{
  "event": "agent.activity",
  "data": {
    "message": "Investigating a new AI framework",
    "status": "running",
    "mission_id": "mission_001"
  }
}
```

Other event types:

- `agent.status_changed`
- `source.discovered`
- `source.check_completed`
- `discovery.created`
- `investigation.started`
- `investigation.completed`
- `report.generated`
- `notification.created`
- `run.failed`

WebSockets are for live updates, not for storing permanent activity history. Save events in PostgreSQL first.

## 13. System Health

| Method | Endpoint        | What it does                         |
| ------ | --------------- | ------------------------------------ |
| GET    | `/health`       | Checks whether FastAPI is responding |
| GET    | `/health/ready` | Checks database and queue readiness  |

---

## Important implementation rules

1. Use `/api/v1` as the API prefix.
2. Validate requests using Pydantic models.
3. Use SQLAlchemy 2.x and Alembic migrations.
4. Use PostgreSQL as the source of truth.
5. Return HTTP 202 Accepted for long-running background operations.
6. Return a `run_id` whenever an asynchronous workflow is started.
7. Use Redis and background workers for collection and investigation.
8. Use LangGraph internally for agent workflows.
9. Save execution activity and reports in PostgreSQL.
10. Apply owner-level data isolation even in the personal version.

## Suggested response convention

A long-running request should return:

```json
{
  "run_id": "run_001",
  "status": "queued",
  "message": "Operation scheduled successfully"
}
```

The frontend can then subscribe to WebSocket updates or poll:

`GET /runs/run_001`

This is the proposed complete API contract for Sentinel AI.
