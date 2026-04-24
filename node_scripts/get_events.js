'use strict';
/**
 * Bridge script: fetch events from Prism FM API.
 *
 * Usage: node get_events.js '<json_args>'
 *
 * JSON args (all optional):
 *   startDate    - YYYY-MM-DD
 *   endDate      - YYYY-MM-DD
 *   eventStatus  - array of EventStatus values (0=HOLD,2=CONFIRMED,3=IN_SETTLEMENT,4=SETTLED)
 *   lastUpdated  - YYYY-MM-DD
 *   showType     - 'all' | 'rental' | 'talent'
 *   includeArchivedEvents - boolean
 *
 * Outputs JSON array of event summary objects to stdout.
 * Errors go to stderr; exit code 1 on failure.
 *
 * Requires PRISM_TOKEN environment variable.
 */

const sdk = require('@prismfm/prism-sdk');
const { getPrismSDK } = sdk.default || sdk;

const rawArgs = process.argv[2] || '{}';
let args;
try {
  args = JSON.parse(rawArgs);
} catch (e) {
  process.stderr.write('Invalid JSON args: ' + e.message + '\n');
  process.exit(1);
}

function summarizeEvent(event) {
  return {
    id: event.id,
    name: event.name,
    event_status: event.eventStatus,
    event_status_string: event.eventStatusString,
    first_date: event.firstDate,
    last_date: event.lastDate,
    date_range_string: event.dateRangeString,
    venue_id: event.venueId,
    venue_name: event.venueName,
    venue_address: event.venueAddress,
    venue_city: event.venueCity,
    venue_state: event.venueState,
    stage_names: event.stageNames,
    is_archived: event.isArchived,
    is_rental: event.isForRentalEvent,
    tour_name: event.tourName,
    number_of_shows: event.numberOfShows,
    capacity: event.capacity,
    event_last_updated: event.eventLastUpdated,
    event_created_date: event.eventCreatedDate,
    age_limit: event.ageLimit,
    ticketing_url: event.ticketingURL,
    // Per-date schedule: [{date, allDay, startTime, endTime, stageName}, ...]
    dates: Array.isArray(event.dates) ? event.dates : [],
  };
}

async function main() {
  const prism = getPrismSDK({});
  const events = await prism.getEvents(args, {
    onProgress: (p) => process.stderr.write(p.toString() + '\n'),
  });
  const summaries = events.map(summarizeEvent);
  process.stdout.write(JSON.stringify(summaries));
}

main().catch((err) => {
  const errData = {
    error: err.message,
    name: err.name,
    validationErrors: err.validationErrors || null,
  };
  process.stderr.write(JSON.stringify(errData) + '\n');
  process.exit(1);
});
