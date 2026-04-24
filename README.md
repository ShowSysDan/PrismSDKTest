# Prism FM SDK — Flask Integration

A Python/Flask + SQLite web application that wraps the [Prism FM](https://prism.fm) Node.js SDK.  It lets you:

- Poll the Prism API for **events in the next 30 days** (or any window you choose)
- Browse events **organised by venue / theater**
- List all **venues and their stages**
- Retrieve **start/end times and run-of-show** items for any date range
- **Write run-of-show items** to a local cache with full duplicate detection
- Manage your **API token via the web UI** — no file editing required

Data is fetched by calling thin Node.js bridge scripts that wrap the official `@prismfm/prism-sdk` package.  Results are cached in a local SQLite database so the Flask REST API is fast and doesn't hammer the Prism API on every request.

---

## Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation — complete from git clone](#installation--complete-from-git-clone)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
- [Web UI](#web-ui)
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
│         Browser UI  /  Flask REST API                │
│  /  /settings  /api/events  /api/venues  /api/ros    │
└────────────────────┬────────────────────────────────┘
                     │ reads
                     ▼
              ┌─────────────┐
              │  SQLite DB  │  instance/prism.db
              │  (cache +   │  · events, venues, stages
              │   settings) │  · run_of_show_items
              └──────┬──────┘  · settings (API token)
                     │ populated by
                     ▼
         ┌──────────────────────────┐
         │  POST /api/sync/*        │  (or click Sync in the UI)
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
| Python     | 3.11           | Uses `str \| None` union syntax |
| Node.js    | 18             | Tested with v22; install via nvm (see below) |
| npm        | 9              | Comes bundled with Node.js |
| Prism API token | —        | Generate in Prism → Settings → Developer |

---

## Installation — complete from git clone

Follow these steps from a fresh clone to a running server.  Everything is
installed inside the project's own virtual environment so it won't touch your
system Python or Node.js.

### 1. Clone the repository

```bash
git clone <repo-url> ~/PrismSDKTest
cd ~/PrismSDKTest
```

### 2. Install Node.js (if not already installed)

Check first — you may already have it:

```bash
node --version   # should print v18.x.x or higher
npm --version
```

If either command says `command not found`, install Node.js via **nvm**
(Node Version Manager).  nvm installs entirely in your home folder — no
`sudo` required:

```bash
# Download and run the nvm installer
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Reload your shell so the nvm command is available
source ~/.bashrc      # or: source ~/.zshrc  if you use zsh

# Install Node.js 22 (LTS) and set it as the default
nvm install 22
nvm use 22

# Confirm
node --version   # v22.x.x
npm --version    # 10.x.x
```

> **Tip:** Add `nvm use 22` to your `~/.bashrc` / `~/.zshrc` so the right
> Node version is selected automatically in every new terminal.

### 3. Create a Python virtual environment

```bash
python3 -m venv venv
```

### 4. Activate the virtual environment

```bash
source venv/bin/activate
```

> Add this line to your `~/.bashrc` or `~/.zshrc` if you want the venv to
> activate automatically whenever you `cd` into the project:
> ```bash
> # in ~/.bashrc
> cd() { builtin cd "$@" && [[ -f venv/bin/activate ]] && source venv/bin/activate; }
> ```

You should now see `(venv)` at the start of your prompt.  All subsequent
commands assume the venv is active.

### 5. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs Flask and python-dotenv — the only two Python dependencies.

### 6. Install the Node.js SDK

The Prism SDK is bundled in `prismfm-prism-sdk-1.1.2/`.  Run `npm install`
inside the bridge-scripts folder to link it into `node_modules`:

```bash
cd node_scripts
npm install
cd ..
```

No internet connection is required — the SDK is a pre-compiled local package.

### 7. Set up your environment file

```bash
cp .env.example .env
```

At a minimum, open `.env` and set your Prism API token:

```dotenv
PRISM_TOKEN=your-prism-api-token-here
```

See [Configuration](#configuration) for all options.  You can also set the
token through the **web UI** after the app is running — see [Web UI](#web-ui).

### 8. Create the instance directory

```bash
mkdir -p instance
```

The SQLite database (`instance/prism.db`) is created automatically on first
startup.

### 9. Start the app

```bash
python run.py
```

Open **http://127.0.0.1:6161** in your browser.  The dashboard shows sync
buttons and links to every API endpoint.

---

## Configuration

All configuration is read from environment variables.  The easiest way to set
them is via the `.env` file in the project root (loaded by `python-dotenv` at
startup).

| Variable | Default | Description |
|----------|---------|-------------|
| `PRISM_TOKEN` | *(empty)* | Prism API token — can also be set via the web UI. |
| `FLASK_DEBUG` | `0` | Set to `1` for hot-reload and detailed error pages. |
| `SECRET_KEY` | `dev-secret-…` | Flask secret key — change this in production. |
| `DATABASE_PATH` | `instance/prism.db` | Path to the SQLite file. |
| `NODE_SCRIPTS_DIR` | `node_scripts` | Directory containing the JS bridge scripts. |
| `NODE_TIMEOUT` | `300` | Seconds before a Node.js call is killed. |
| `DEFAULT_LOOKAHEAD_DAYS` | `30` | Default event window when `days` is not specified. |

### Token resolution order

When making API calls, the token is picked up in this order:

1. **Database** — token saved via the Settings page in the web UI
2. **Environment variable** — `PRISM_TOKEN` in `.env` or your shell
3. None — API calls return 502 errors

### Prism token scopes

The token needs at least these read-only scopes:

| Scope | Used by |
|-------|---------|
| `read-events` | `/api/sync/events` |
| `read-venues` | `/api/sync/venues` |
| `read-run-of-show` | `/api/sync/run-of-show` |

---

## Running the app

With the venv active and `.env` populated:

```bash
python run.py
```

For auto-reload during development:

```bash
FLASK_DEBUG=1 python run.py
# or
flask --app run:app run --debug
```

---

## Web UI

The app ships with a minimal browser interface at **http://127.0.0.1:6161**.

### Dashboard `/`

- Shows the number of cached venues, events, and run-of-show items
- One-click **Sync** buttons for venues, events (30 days), and run-of-show
- Table of every API endpoint with clickable links for GET routes

### Settings `/settings`

- **Set or swap your API token** — paste in a new token and click Save.
  The token is stored in the local SQLite database and takes effect
  immediately without a restart.
- Shows which token source is active (database vs. environment variable)
- Displays current runtime configuration values

The token is masked in the UI — only the last 6 characters are shown.

---

## API Reference

All `/api/*` endpoints return `Content-Type: application/json`.

### Health check

#### `GET /api/health`

Quick status check — confirms the app is running, reports token presence, and
shows row counts for each table.

```bash
curl http://localhost:6161/api/health
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
up-to-date data.  You can also use the Sync buttons on the dashboard.

#### `POST /api/sync/events`

Fetch events from Prism for a date window and upsert them into the local cache.

```bash
# Sync the next 30 days (default)
curl -X POST http://localhost:6161/api/sync/events

# Sync the next 60 days, confirmed events only
curl -X POST http://localhost:6161/api/sync/events \
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
curl -X POST http://localhost:6161/api/sync/venues
```

**Response**

```json
{ "synced": 12, "errors": [] }
```

---

#### `POST /api/sync/run-of-show`

Fetch run-of-show items for a date window.  Existing API items in the window
are deleted first so stale items don't accumulate.  Locally-written items are
**never** overwritten by a sync.

```bash
curl -X POST http://localhost:6161/api/sync/run-of-show \
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

All event read endpoints serve data **from the local SQLite cache**.
Run `POST /api/sync/events` (or click the Sync button) first.

#### `GET /api/events`

List upcoming events.

```bash
# Next 30 days (default)
curl http://localhost:6161/api/events

# Next 60 days, confirmed events only
curl "http://localhost:6161/api/events?days=60&status=2"

# Events at a specific venue
curl "http://localhost:6161/api/events?venue_id=123"

# Multiple statuses
curl "http://localhost:6161/api/events?status=2&status=3"
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
      "synced_at": "2025-05-20 10:30:00"
    }
  ]
}
```

---

#### `GET /api/events/by-venue`

Events grouped by venue — ideal for a theatre/schedule overview.

```bash
curl "http://localhost:6161/api/events/by-venue?days=30&status=2"
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
    }
  ]
}
```

---

#### `GET /api/events/<id>`

Single event by its Prism ID.

```bash
curl http://localhost:6161/api/events/1490700
```

Returns the full cached event object or `404` if not in cache.

---

### Venues

#### `GET /api/venues`

List all cached venues with their stages.

```bash
curl http://localhost:6161/api/venues
curl "http://localhost:6161/api/venues?include_inactive=true"
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
      "timezone": "America/Los_Angeles",
      "capacity": 500,
      "stages": [
        {"id": 201, "venue_id": 101, "name": "Main Stage", "capacity": 500, "color": "#FF0000"}
      ]
    }
  ]
}
```

---

#### `GET /api/venues/<id>`

Single venue with its stages.

```bash
curl http://localhost:6161/api/venues/101
```

---

#### `GET /api/venues/<id>/events`

Upcoming events at a specific venue.

```bash
curl "http://localhost:6161/api/venues/101/events?days=60&status=2"
```

---

### Run of show

Run-of-show items represent the **detailed schedule within an event** — load-in,
doors, support acts, headliner, load-out, etc.

#### `GET /api/run-of-show`

List run-of-show items from the local cache.

```bash
# Default: today through today + 30 days
curl http://localhost:6161/api/run-of-show

# Custom window
curl "http://localhost:6161/api/run-of-show?start_date=2025-06-15&end_date=2025-06-15"

# Filter by venue
curl "http://localhost:6161/api/run-of-show?venue_id=101"

# Only locally-written items
curl "http://localhost:6161/api/run-of-show?source=local"
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

#### `POST /api/run-of-show/items`

Add a locally-managed run-of-show item.

> **Note:** The Prism API does not currently expose a write endpoint for
> run-of-show items, so items created here are stored **only in the local
> SQLite cache** (`source = "local"`).  They appear alongside API-fetched
> items in `GET /api/run-of-show` responses.

**Duplicate detection**

A `409 Conflict` is returned when the combination of `event_id` + `title` +
`occurs_at` + `stage_id` already exists (for both `api` and `local` items).
The response includes the `existing_id` so you can fetch or update it.

```bash
curl -X POST http://localhost:6161/api/run-of-show/items \
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

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | **Yes** | Display name (e.g. "Doors", "Load In") |
| `occurs_at` | string | **Yes** | ISO datetime or plain date (`YYYY-MM-DD`) |
| `event_id` | int | **Yes** | Prism event ID |
| `finishes_at` | string | No | ISO datetime when the item ends |
| `venue_id` | int | No | Venue ID |
| `stage_id` | int | No | Stage ID |
| `event_name` | string | No | Human-readable event name |
| `venue_name` | string | No | Human-readable venue name |
| `stage_name` | string | No | Human-readable stage name |
| `event_description` | string | No | Free-text notes |

| Code | Meaning |
|------|---------|
| 201  | Created — body contains the new item |
| 400  | Missing required fields or invalid JSON |
| 409  | Duplicate — `existing_id` in body |

---

#### `DELETE /api/run-of-show/items/<id>`

Delete a locally-created run-of-show item.  Only `source = "local"` items
can be deleted this way.

```bash
curl -X DELETE http://localhost:6161/api/run-of-show/items/42
```

| Code | Meaning |
|------|---------|
| 200  | Deleted |
| 403  | Cannot delete API-sourced items |
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
│       └── sample-scripts/        # Official usage examples
│
├── node_scripts/                  # Node.js bridge scripts
│   ├── package.json               # Declares @prismfm/prism-sdk dependency
│   ├── node_modules/              # (generated by npm install — git-ignored)
│   ├── get_events.js              # Calls prism.getEvents()
│   ├── get_venues.js              # Calls prism.getVenues()
│   └── get_run_of_show.js         # Calls prism.getRunOfShow()
│
├── app/                           # Flask application package
│   ├── __init__.py                # App factory, blueprint registration
│   ├── database.py                # SQLite schema, upsert & settings helpers
│   ├── sdk_bridge.py              # Python → Node.js subprocess wrapper
│   ├── templates/
│   │   ├── base.html              # Shared nav, CSS layout
│   │   ├── index.html             # Dashboard
│   │   └── settings.html          # Token & config settings
│   └── routes/
│       ├── ui.py                  # Browser UI: / and /settings
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
├── requirements.txt               # Python dependencies (Flask, python-dotenv)
├── .env.example                   # Environment variable template
├── .env                           # Your local config (git-ignored)
├── .gitignore
└── README.md
```

---

## Troubleshooting

### `node: command not found` or `npm: command not found`
Node.js is not installed (or nvm hasn't been sourced in the current shell).

```bash
# Install nvm (one-time)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc      # reload shell

# Install and activate Node 22
nvm install 22
nvm use 22

node --version   # v22.x.x
npm --version    # 10.x.x
```

Then re-run `cd node_scripts && npm install && cd ..`.

### Token not working / 502 errors from sync
1. Open **http://localhost:6161/settings** and check which source is active.
2. Paste in your token and click **Save Token**.
3. Verify the token has the right scopes (`read-events`, `read-venues`, `read-run-of-show`).
4. Test the token directly:
   ```bash
   PRISM_TOKEN=your-token node node_scripts/get_venues.js '{}'
   ```

### Sync times out
Large event datasets can take several minutes.  Increase `NODE_TIMEOUT` in `.env`:
```dotenv
NODE_TIMEOUT=600   # 10 minutes
```

### `(venv)` prompt disappeared / `ModuleNotFoundError: No module named 'flask'`
Your venv is not active:
```bash
source ~/PrismSDKTest/venv/bin/activate
```

### Empty results from read endpoints
Read endpoints serve from the local SQLite cache — you must sync first:
```bash
curl -X POST http://localhost:6161/api/sync/venues
curl -X POST http://localhost:6161/api/sync/events
curl -X POST http://localhost:6161/api/sync/run-of-show \
  -H "Content-Type: application/json" \
  -d '{"start_date":"2025-06-01","end_date":"2025-06-30"}'
```
Or use the **Sync** buttons on the dashboard at **http://localhost:6161**.

### Database errors after a schema change
Delete the database file and restart — it is recreated automatically:
```bash
rm instance/prism.db
python run.py
```
