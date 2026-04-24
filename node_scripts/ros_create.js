'use strict';
/**
 * Bridge script: create a run-of-show item in Prism.
 *
 * Usage: node ros_create.js '<json_args>'
 *
 * Required args:
 *   event_id   - int
 *   title      - string
 *   start_time - "HH:MM" or "HH:MM:SS"
 *
 * Optional args:
 *   stage_id   - int
 *   duration   - int (seconds, default 0)
 *
 * Outputs the created item JSON to stdout.
 */

const sdk = require('@prismfm/prism-sdk');
const { getPrismSDK } = sdk.default || sdk;

async function main() {
  const args = JSON.parse(process.argv[2] || '{}');
  if (!args.event_id || !args.title || !args.start_time) {
    throw new Error('event_id, title, and start_time are required');
  }

  // Normalise to HH:MM:SS
  let t = String(args.start_time).trim();
  if (/^\d{1,2}:\d{2}$/.test(t)) t += ':00';

  const prism = getPrismSDK({});
  const result = await prism.callPrismApi(
    `/events/${args.event_id}/run-of-show`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        offset: 0,
        duration: args.duration || 0,
        include_in_all_docs: true,
        event_talent_id: null,
        id: null,
        stage_id: args.stage_id || null,
        start_time: t,
        title: args.title,
        event_id: args.event_id,
      }),
    }
  );
  process.stdout.write(JSON.stringify(result));
}

main().catch(err => {
  process.stderr.write(JSON.stringify({ error: err.message }) + '\n');
  process.exit(1);
});
