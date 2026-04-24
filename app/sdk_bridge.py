"""
Python wrapper around the Node.js Prism SDK bridge scripts.

Each public function spawns a short-lived Node.js process, passes query
parameters as a JSON string, and returns the parsed response.  All SDK
errors are translated into SDKError exceptions so callers get a
consistent interface regardless of the underlying failure mode.
"""

import json
import os
import subprocess
from typing import Any

from config import Config


def _resolve_token() -> str:
    """
    Return the Prism API token, preferring the value stored in the
    database settings table over the PRISM_TOKEN environment variable.
    This lets the UI token override take effect without a restart.
    """
    try:
        from .database import get_db, get_setting
        db = get_db(Config.DATABASE_PATH)
        token = get_setting(db, "prism_token")
        if token:
            return token
    except Exception:
        pass
    return Config.PRISM_TOKEN


class SDKError(Exception):
    """Raised when a Prism SDK bridge script returns a non-zero exit code."""

    def __init__(self, message: str, validation_errors: dict | None = None):
        super().__init__(message)
        self.validation_errors = validation_errors or {}


def _call(script_name: str, args: dict | None = None, timeout: int | None = None) -> Any:
    """
    Invoke a Node.js bridge script and return the parsed JSON response.

    Parameters
    ----------
    script_name : str
        Filename of the bridge script (e.g. ``"get_events.js"``).
    args : dict, optional
        Query parameters forwarded to the script as a JSON string.
    timeout : int, optional
        Override the default NODE_TIMEOUT (seconds).

    Returns
    -------
    Any
        Parsed JSON value from the script's stdout.

    Raises
    ------
    SDKError
        If the script exits with a non-zero code or stdout cannot be parsed.
    """
    scripts_dir = Config.NODE_SCRIPTS_DIR
    script_path = os.path.join(scripts_dir, script_name)

    if not os.path.isfile(script_path):
        raise SDKError(f"Bridge script not found: {script_path}")

    cmd = ["node", script_name, json.dumps(args or {})]
    effective_timeout = timeout or Config.NODE_TIMEOUT

    env = {**os.environ, "PRISM_TOKEN": _resolve_token()}

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            env=env,
            cwd=scripts_dir,
        )
    except subprocess.TimeoutExpired:
        raise SDKError(
            f"SDK call timed out after {effective_timeout}s ({script_name})"
        )
    except FileNotFoundError:
        raise SDKError(
            "node executable not found – make sure Node.js ≥ 18 is installed and on PATH"
        )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # The bridge scripts write a JSON error object to stderr
        try:
            err_obj = json.loads(stderr)
            raise SDKError(
                err_obj.get("error", stderr),
                err_obj.get("validationErrors"),
            )
        except (json.JSONDecodeError, KeyError):
            raise SDKError(stderr or f"Script exited with code {result.returncode}")

    stdout = result.stdout.strip()
    if not stdout:
        raise SDKError(f"Script produced no output ({script_name})")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SDKError(f"Could not parse script output as JSON: {exc}")


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_events(
    start_date: str | None = None,
    end_date: str | None = None,
    event_status: list[int] | None = None,
    last_updated: str | None = None,
    show_type: str | None = None,
    include_archived: bool = False,
) -> list[dict]:
    """
    Fetch event summaries from Prism.

    Parameters
    ----------
    start_date : str, optional
        Filter events starting on or after this date (YYYY-MM-DD).
    end_date : str, optional
        Filter events ending on or before this date (YYYY-MM-DD).
    event_status : list[int], optional
        One or more EventStatus values.
        0=HOLD, 2=CONFIRMED, 3=IN_SETTLEMENT, 4=SETTLED
    last_updated : str, optional
        Return only events modified after this date (YYYY-MM-DD).
    show_type : str, optional
        'all' | 'rental' | 'talent'
    include_archived : bool
        Include archived events (default False).

    Returns
    -------
    list[dict]
        List of event summary dicts (see get_events.js for exact shape).
    """
    args: dict = {}
    if start_date:
        args["startDate"] = start_date
    if end_date:
        args["endDate"] = end_date
    if event_status:
        args["eventStatus"] = event_status
    if last_updated:
        args["lastUpdated"] = last_updated
    if show_type:
        args["showType"] = show_type
    if include_archived:
        args["includeArchivedEvents"] = True

    return _call("get_events.js", args)


def fetch_venues(include_inactive: bool = False) -> list[dict]:
    """
    Fetch venue records from Prism.

    Parameters
    ----------
    include_inactive : bool
        When True, inactive venues are included in the result.

    Returns
    -------
    list[dict]
        Full Venue objects as returned by the Prism API.
    """
    args: dict = {}
    if include_inactive:
        args["includeInactive"] = True
    return _call("get_venues.js", args)


def fetch_run_of_show(
    start_date: str,
    end_date: str,
    stage_ids: list[int] | None = None,
    venue_ids: list[int] | None = None,
    talent_agent_ids: list[int] | None = None,
    event_tag_ids: list[int] | None = None,
) -> list[dict]:
    """
    Fetch run-of-show items from Prism.

    Parameters
    ----------
    start_date : str
        Start of the date window (YYYY-MM-DD). **Required.**
    end_date : str
        End of the date window (YYYY-MM-DD). **Required.**
    stage_ids : list[int], optional
        Restrict to specific stage IDs.
    venue_ids : list[int], optional
        Restrict to specific venue IDs.
    talent_agent_ids : list[int], optional
        Restrict to specific talent agent IDs.
    event_tag_ids : list[int], optional
        Restrict to events bearing specific tag IDs.

    Returns
    -------
    list[dict]
        List of RunOfShowItem dicts.
    """
    args: dict = {"startDate": start_date, "endDate": end_date}
    if stage_ids:
        args["stageIds"] = stage_ids
    if venue_ids:
        args["venueIds"] = venue_ids
    if talent_agent_ids:
        args["talentAgentIds"] = talent_agent_ids
    if event_tag_ids:
        args["eventTagIds"] = event_tag_ids
    return _call("get_run_of_show.js", args)


def prism_create_ros_item(
    event_id: int,
    title: str,
    start_time: str,
    stage_id: int | None = None,
    duration: int = 0,
) -> dict:
    """Create a run-of-show item in Prism via the web API."""
    return _call("ros_create.js", {
        "event_id": event_id,
        "title": title,
        "start_time": start_time,
        "stage_id": stage_id,
        "duration": duration,
    }, timeout=30)


def prism_delete_ros_item(event_id: int, item_id: int) -> dict:
    """Delete a run-of-show item from Prism."""
    return _call("ros_delete.js", {
        "event_id": event_id,
        "item_id": item_id,
    }, timeout=30)


def prism_update_ros_item(
    event_id: int,
    item_id: int,
    title: str | None = None,
    start_time: str | None = None,
    stage_id: int | None = None,
    duration: int = 0,
) -> dict:
    """Update a run-of-show item in Prism."""
    return _call("ros_update.js", {
        "event_id": event_id,
        "item_id": item_id,
        "title": title,
        "start_time": start_time,
        "stage_id": stage_id,
        "duration": duration,
    }, timeout=30)
