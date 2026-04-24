# Prism FM SDK — Flask Integration

A Python/Flask + SQLite web application that wraps the [Prism FM](https://prism.fm) Node.js SDK.  It lets you:

- Poll the Prism API for **events in the next 30 days** (or any window you choose)
- Browse events **organised by venue / theater**
- List all **venues and their stages**
- Retrieve **start/end times and run-of-show** items for any date range
- **Write run-of-show items** to a local cache with full duplicate detection

Data is fetched by calling thin Node.js bridge scripts that wrap the official `@prismfm/prism-sdk` package.  Results are cached in a local SQLite database so the Flask REST API is fast and doesn't hammer the Prism API on every request.

---

## Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
- [API Reference](#api-reference)
  - [Health check](#health-check)
  - [Sync endpoints](#sync-endpoints)
  - [Events](#events)
  - [Venues](#venues)
  - [Run of show](#run-of-show)
- [Event status codes](#event-status-codes)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Flask REST API                     │
│  /api/events  /api/venues  /api/run-of-show          │
└────────────────────┬────────────────────────────────┘
                     │ reads
                     ▼
              ┌─────────────┐
              │  SQLite DB  │  instance/prism.db
              │  (cache)    │
              └──────┬──────┘
                     │ populated by
                     ▼
         ┌──────────────────────────┐
         │  POST /api/sync/*        │
         └────────────┬─────────────┘
                      │ subprocess
                      ▼
        ┌──────────────────────────────┐
        │  Node.js bridge scripts      │
        │  node_scripts/get_events.js  │
        │  node_scripts/get_venues.js  │
        │  node_scripts/get_ros.js     │
        └────────────┬─────────────────┘
                     │ @prismfm/prism-sdk
                     ▼
             ┌───────────────┐
             │  Prism FM API │
             └───────────────┘
```

**Why Node.js + Python?**
The official Prism SDK is TypeScript/Node.js only.  Rather than reimplementing the API layer, we call the compiled SDK from Python via subprocess.  Each bridge script accepts JSON args, writes JSON to stdout, and exits — so Python can call it synchronously with `subprocess.run()`.

**Why SQLite?**
Prism event fetches can take 30–60 seconds for large datasets.  Caching in SQLite means the Flask API responds in milliseconds for read queries, and you control when to refresh data via the `/api/sync/*` endpoints.

---

## Prerequisites

| Dependency | Minimum version | Notes |
|------------|----------------|-------|
| Python     | 3.11           | Uses `str \| None` syntax |
| Node.js    | 18             | Tested with v22 |
| npm        | 9              | For installing the Prism SDK |
| Prism API token | —        | Generate in Prism > Settings > Developer |

---

## Installation

These instructions install everything into a Python virtual environment in your home folder.  Adjust the path if you prefer a different location.

### 1. Clone / download the project

```bash
# If you haven't already:
git clone <repo-url> ~/PrismSDKTest
cd ~/PrismSDKTest
```

### 2. Create and activate a Python virtual environment

```bash
python3 -m venv ~/PrismSDKTest/venv
source ~/PrismSDKTest/venv/bin/activate
```

> **Tip:** Add `source ~/PrismSDKTest/venv/bin/activate` to your shell profile
> (`.bashrc` / `.zshrc`) so the venv activates automatically when you open a
> terminal in this directory.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the Node.js SDK

The SDK is already extracted in the `prismfm-prism-sdk-1.1.2/` directory.  Run
`npm install` inside the bridge-scripts folder to link it:

```bash
cd node_scripts
npm install
cd ..
```

This creates `node_scripts/node_modules/@prismfm/prism-sdk` — a reference to
the local SDK package.  No internet connection is required.

### 5. Configure your environment

```bash
cp .env.example .env
```

Open `.env` and set your Prism API token:

```dotenv
PRISM_TOKEN=your-prism-api-token-here
```

See [Configuration](#configuration) for all available options.

### 6. Create the instance directory

```bash
mkdir -p instance
```

The SQLite database (`instance/prism.db`) is created automatically the first
time the app starts.

---

## Configuration

All configuration is read from environment variables.  The easiest way to set
them is via a `.env` file in the project root (loaded by `python-dotenv`).

| Variable | Default | Description |
|----------|---------|-------------|
| `PRISM_TOKEN` | *(empty)* | **Required.** Your Prism FM API token. |
| `FLASK_DEBUG` | `0` | Set to `1` for hot-reload and detailed error pages. |
| `SECRET_KEY` | `dev-secret-…` | Flask secret key — change this in production. |
| `DATABASE_PATH` | `instance/prism.db` | Path to the SQLite file. |
| `NODE_SCRIPTS_DIR` | `node_scripts` | Directory containing the bridge scripts. |
| `NODE_TIMEOUT` | `300` | Seconds before a Node.js call is killed (raise for large datasets). |
| `DEFAULT_LOOKAHEAD_DAYS` | `30` | Default event window when `days` is not specified. |

### Prism token scopes

The token needs at least these read-only scopes:

| Scope | Used by |
|-------|---------|
| `read-events` | `/api/sync/events` |
| `read-venues` | `/api/sync/venues` |
| `read-run-of-show` | `/api/sync/run-of-show` |

---

## Running the app

Make sure your venv is active and `.env` is populated, then:

```bash
python run.py
```

The API is available at `http://127.0.0.1:5000`.

For auto-reload during development:

```bash
FLASK_DEBUG=1 python run.py
# or
flask --app run:app run --debug
```

---

## API Reference

All endpoints return `Content-Type: application/json`.

### Health check

#### `GET /api/health`

Quick status check — confirms the app is running, reports token presence, and
shows the row counts in each table.

```bash
curl http://localhost:5000/api/health
```

```json
{
  "status": "ok",
  "prism_token_set": true,
  "last_events_sync": "2025-06-01 14:32:10",
  "table_stats": {
    "venues_count": 12,
    "events_count": 47,
    "run_of_show_items_count": 183
  }
}
```

---

### Sync endpoints

Sync endpoints **pull fresh data from the Prism API** and store it in SQLite.
Call these before querying the read endpoints, and again whenever you want
up-to-date data.

#### `POST /api/sync/events`

Fetch events from Prism for a date window and upsert them into the local cache.

```bash
# Sync the next 30 days (default)
curl -X POST http://localhost:5000/api/sync/events

# Sync the next 60 days, confirmed events only
curl -X POST http://localhost:5000/api/sync/events \
  -H "Content-Type: application/json" \
  -d '{"days": 60, "status": [2]}'
```

**Request body (JSON, all optional)**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | 30 | How many days from today to fetch |
| `status` | int[] | *(all)* | EventStatus filter (see [status codes](#event-status-codes)) |
| `show_type` | string | *(all)* | `"all"` \| `"rental"` \| `"talent"` |
| `include_archived` | bool | false | Include archived events |

**Response**

```json
{
  "synced": 47,
  "window": {"start": "2025-06-01", "end": "2025-07-01"},
  "errors": []
}
```

---

#### `POST /api/sync/venues`

Fetch venues from Prism (with all stages) and upsert them into the local cache.

```bash
# Sync active venues only (default)
curl -X POST http://localhost:5000/api/sync/venues

# Include inactive venues
curl -X POST http://localhost:5000/api/sync/venues \
  -H "Content-Type: application/json" \
  -d '{"include_inactive": true}'
```

**Response**

```json
{
  "synced": 12,
  "errors": []
}
```

---

#### `POST /api/sync/run-of-show`

Fetch run-of-show items for a date window.  Existing API items in the window
are deleted first so stale items don't accumulate.  Locally-written items are
**never** overwritten by a sync.

```bash
curl -X POST http://localhost:5000/api/sync/run-of-show \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2025-06-01", "end_date": "2025-06-30"}'
```

**Request body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_date` | string | **Yes** | YYYY-MM-DD |
| `end_date` | string | **Yes** | YYYY-MM-DD |
| `venue_ids` | int[] | No | Restrict to these venues |
| `stage_ids` | int[] | No | Restrict to these stages |

**Response**

```json
{
  "synced": 93,
  "skipped_duplicates": 0,
  "window": {"start": "2025-06-01", "end": "2025-06-30"},
  "errors": []
}
```

---

### Events

All event read endpoints serve data **from the local SQLite cache**.  Run
`POST /api/sync/events` first.

#### `GET /api/events`

List upcoming events.

```bash
# Next 30 days (default)
curl http://localhost:5000/api/events

# Next 60 days, confirmed events only
curl "http://localhost:5000/api/events?days=60&status=2"

# Events at a specific venue
curl "http://localhost:5000/api/events?venue_id=123"

# Multiple statuses
curl "http://localhost:5000/api/events?status=2&status=3"
```

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Look-ahead window in days |
| `status` | int | *(all)* | EventStatus filter; may be repeated |
| `venue_id` | int | *(all)* | Restrict to a specific venue |

**Response**

```json
{
  "total": 47,
  "window": {"start": "2025-06-01", "end": "2025-07-01"},
  "events": [
    {
      "id": 1490700,
      "name": "Artist Name",
      "event_status": 2,
      "event_status_string": "Confirmed",
      "status_label": "CONFIRMED",
      "first_date": "2025-06-15",
      "last_date": "2025-06-15",
      "date_range_string": "June 15, 2025",
      "venue_id": 101,
      "venue_name": "The Roxy Theatre",
      "venue_city": "Los Angeles",
      "venue_state": "CA",
      "stage_names": "Main Stage",
      "capacity": 500,
      "ticketing_url": "https://...",
      ...
    }
  ]
}
```

---

#### `GET /api/events/by-venue`

Events grouped by venue — great for a theatre/schedule overview.

```bash
curl "http://localhost:5000/api/events/by-venue?days=30&status=2"
```

**Response**

```json
{
  "total_events": 47,
  "window": {"start": "2025-06-01", "end": "2025-07-01"},
  "venues": [
    {
      "venue_id": 101,
      "venue_name": "The Roxy Theatre",
      "venue_city": "Los Angeles",
      "venue_state": "CA",
      "event_count": 8,
      "events": [ {...}, {...} ]
    },
    {
      "venue_id": 102,
      "venue_name": "House of Blues",
      ...
    }
  ]
}
```

---

#### `GET /api/events/<id>`

Single event by its Prism ID.

```bash
curl http://localhost:5000/api/events/1490700
```

Returns the full cached event object or `404` if not in cache.

---

### Venues

#### `GET /api/venues`

List all cached venues with their stages.

```bash
# Active venues only (default)
curl http://localhost:5000/api/venues

# Include inactive venues
curl "http://localhost:5000/api/venues?include_inactive=true"
```

**Response**

```json
{
  "total": 12,
  "venues": [
    {
      "id": 101,
      "name": "The Roxy Theatre",
      "active": 1,
      "city": "Los Angeles",
      "state": "CA",
      "country": "US",
      "address": "9009 Sunset Blvd",
      "timezone": "America/Los_Angeles",
      "capacity": 500,
      "currency": "USD",
      "stages": [
        {"id": 201, "venue_id": 101, "name": "Main Stage", "active": 1, "capacity": 500, "color": "#FF0000"},
        {"id": 202, "venue_id": 101, "name": "Acoustic Room", "active": 1, "capacity": 150, "color": "#00FF00"}
      ]
    }
  ]
}
```

---

#### `GET /api/venues/<id>`

Single venue with its stages.

```bash
curl http://localhost:5000/api/venues/101
```

---

#### `GET /api/venues/<id>/events`

Upcoming events at a specific venue.

```bash
# Next 30 days
curl http://localhost:5000/api/venues/101/events

# Confirmed only, next 60 days
curl "http://localhost:5000/api/venues/101/events?days=60&status=2"
```

---

### Run of show

Run-of-show items represent the **detailed schedule within an event** — load-in,
doors, support acts, headliner, load-out, etc.

#### `GET /api/run-of-show`

List run-of-show items from the local cache.

```bash
# Default: today through today + 30 days
curl http://localhost:5000/api/run-of-show

# Custom window
curl "http://localhost:5000/api/run-of-show?start_date=2025-06-15&end_date=2025-06-15"

# Specific venue
curl "http://localhost:5000/api/run-of-show?venue_id=101"

# Specific stage
curl "http://localhost:5000/api/run-of-show?stage_id=201"

# Only locally-written items
curl "http://localhost:5000/api/run-of-show?source=local"
```

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | string | today | YYYY-MM-DD |
| `end_date` | string | today+30d | YYYY-MM-DD |
| `venue_id` | int | *(all)* | Filter to a venue |
| `stage_id` | int | *(all)* | Filter to a stage |
| `event_id` | int | *(all)* | Filter to an event |
| `source` | string | *(all)* | `"api"` or `"local"` |

**Response**

```json
{
  "total": 15,
  "window": {"start": "2025-06-15", "end": "2025-06-15"},
  "items": [
    {
      "id": 1,
      "prism_id": 98765,
      "title": "Doors",
      "occurs_at": "2025-06-15T19:00:00Z",
      "finishes_at": "2025-06-15T20:00:00Z",
      "event_id": 1490700,
      "event_name": "Artist Name",
      "event_status": 2,
      "event_status_label": "CONFIRMED",
      "venue_id": 101,
      "venue_name": "The Roxy Theatre",
      "stage_id": 201,
      "stage_name": "Main Stage",
      "event_description": "Doors open to the public",
      "source": "api",
      "created_at": "2025-05-20 10:30:00",
      "synced_at": "2025-05-20 10:30:00"
    }
  ]
}
```

---

#### `GET /api/run-of-show/<id>`

Single run-of-show item by its local database id.

```bash
curl http://localhost:5000/api/run-of-show/1
```

---

#### `POST /api/run-of-show/items`

Add a locally-managed run-of-show item.

> **Note:** The Prism API does not currently expose a write endpoint for
> run-of-show items, so items created here are stored **only in the local
> SQLite cache** (`source = "local"`).  They appear alongside API-fetched
> items in `GET /api/run-of-show` responses.

**Duplicate detection**

The endpoint rejects an item if the combination of `event_id` + `title` +
`occurs_at` + `stage_id` already exists in the database (for both `api` and
`local` items).  A `409 Conflict` response is returned with the id of the
existing item so you can retrieve or update it.

```bash
curl -X POST http://localhost:5000/api/run-of-show/items \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Load In",
    "occurs_at": "2025-06-15T14:00:00",
    "event_id": 1490700,
    "finishes_at": "2025-06-15T16:00:00",
    "venue_id": 101,
    "stage_id": 201,
    "event_name": "Artist Name",
    "venue_name": "The Roxy Theatre",
    "stage_name": "Main Stage",
    "event_description": "Crew load in and production setup"
  }'
```

**Request body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | **Yes** | Display name (e.g. "Doors", "Load In") |
| `occurs_at` | string | **Yes** | ISO datetime (`YYYY-MM-DDThh:mm:ss`) or plain date (`YYYY-MM-DD`) |
| `event_id` | int | **Yes** | Prism event ID this item belongs to |
| `finishes_at` | string | No | ISO datetime when the item ends |
| `venue_id` | int | No | Venue ID |
| `stage_id` | int | No | Stage ID |
| `event_name` | string | No | Human-readable event name (for display) |
| `venue_name` | string | No | Human-readable venue name (for display) |
| `stage_name` | string | No | Human-readable stage name (for display) |
| `event_description` | string | No | Free-text notes |

**Responses**

| Code | Meaning |
|------|---------|
| 201  | Item created; response body contains the new item |
| 400  | Missing required fields or invalid JSON |
| 409  | Duplicate — a matching item already exists |

**201 response**
```json
{
  "id": 42,
  "title": "Load In",
  "occurs_at": "2025-06-15T14:00:00",
  "finishes_at": "2025-06-15T16:00:00",
  "event_id": 1490700,
  "source": "local",
  ...
}
```

**409 response**
```json
{
  "error": "Duplicate run-of-show item",
  "detail": "An item with the same event_id, title, occurs_at, and stage_id already exists (id=42).",
  "existing_id": 42
}
```

---

#### `DELETE /api/run-of-show/items/<id>`

Delete a locally-created run-of-show item.

Only `source = "local"` items can be deleted this way.  API-sourced items are
managed by re-syncing the date range.

```bash
curl -X DELETE http://localhost:5000/api/run-of-show/items/42
```

**Responses**

| Code | Meaning |
|------|---------|
| 200  | Deleted successfully |
| 403  | Cannot delete an API-sourced item |
| 404  | Item not found |

---

## Event status codes

| Value | Constant | Meaning |
|-------|----------|---------|
| 0 | `HOLD` | Tentative hold on the calendar |
| 2 | `CONFIRMED` | Confirmed event |
| 3 | `IN_SETTLEMENT` | Settlement in progress |
| 4 | `SETTLED` | Fully settled |

---

## Project structure

```
PrismSDKTest/
│
├── prismfm-prism-sdk-1.1.2/       # Prism FM SDK (do not modify)
│   └── package/
│       ├── build/dist/index.js    # Compiled, bundled SDK
│       ├── index.d.ts             # TypeScript type definitions
│       └── sample-scripts/        # Official usage examples
│
├── node_scripts/                  # Node.js bridge scripts
│   ├── package.json               # Declares @prismfm/prism-sdk dependency
│   ├── node_modules/              # (generated by npm install)
│   ├── get_events.js              # Calls prism.getEvents()
│   ├── get_venues.js              # Calls prism.getVenues()
│   └── get_run_of_show.js         # Calls prism.getRunOfShow()
│
├── app/                           # Flask application package
│   ├── __init__.py                # App factory, blueprint registration
│   ├── database.py                # SQLite schema, upsert helpers
│   ├── sdk_bridge.py              # Python → Node.js subprocess wrapper
│   └── routes/
│       ├── events.py              # GET /api/events/*
│       ├── venues.py              # GET /api/venues/*
│       ├── run_of_show.py         # GET+POST+DELETE /api/run-of-show/*
│       └── sync.py                # POST /api/sync/*
│
├── instance/
│   └── prism.db                   # SQLite database (auto-created, git-ignored)
│
├── venv/                          # Python virtual environment (git-ignored)
│
├── run.py                         # Flask entry point
├── config.py                      # Configuration class
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
├── .env                           # Your local config (git-ignored)
├── .gitignore
└── README.md
```

---

## Troubleshooting

### `node executable not found`
Make sure Node.js ≥ 18 is installed and on your `PATH`.

```bash
node --version   # should print v18.x.x or higher
```

### `PRISM_TOKEN` is empty / auth errors
- Check that `.env` contains `PRISM_TOKEN=your-token-here`
- Verify the token has the required scopes (`read-events`, `read-venues`, `read-run-of-show`)
- Test the token directly: `PRISM_TOKEN=your-token node node_scripts/get_venues.js '{}'`

### Sync times out
Large event datasets can take several minutes.  Increase `NODE_TIMEOUT` in `.env`:

```dotenv
NODE_TIMEOUT=600   # 10 minutes
```

### `ModuleNotFoundError: No module named 'flask'`
Your venv is not active.  Run:

```bash
source ~/PrismSDKTest/venv/bin/activate
```

### Empty results from read endpoints
The read endpoints serve from the local SQLite cache.  You must sync first:

```bash
curl -X POST http://localhost:5000/api/sync/venues
curl -X POST http://localhost:5000/api/sync/events
curl -X POST http://localhost:5000/api/sync/run-of-show \
  -H "Content-Type: application/json" \
  -d '{"start_date":"2025-06-01","end_date":"2025-06-30"}'
```

### Database errors after a schema change
Delete the database file and restart — it will be recreated automatically:

```bash
rm instance/prism.db
python run.py
```
