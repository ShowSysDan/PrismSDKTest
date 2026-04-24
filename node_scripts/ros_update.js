'use strict';
/**
 * Bridge script: update a run-of-show item in Prism.
 *
 * Usage: node ros_update.js '<json_args>'
 *
 * Required args:  event_id, item_id
 * Optional args:  title, start_time ("HH:MM" or "HH:MM:SS"), stage_id, duration
 */

const { getPrismAndXsrf } = require('./prism_write_auth');

async function main() {
  const args = JSON.parse(process.argv[2] || '{}');
  if (!args.event_id || !args.item_id) {
    throw new Error('event_id and item_id are required');
  }

  let t = args.start_time ? String(args.start_time).trim() : undefined;
  if (t && /^\d{1,2}:\d{2}$/.test(t)) t += ':00';

  const { prism, xsrfToken } = await getPrismAndXsrf();

  const result = await prism.callPrismApi(
    `/events/${args.event_id}/run-of-show/${args.item_id}`,
    {
      method: 'PUT',
      headers: {
        'content-type': 'application/json',
        ...(xsrfToken ? { 'x-xsrf-token': xsrfToken } : {}),
      },
      body: JSON.stringify({
        id:                  args.item_id,
        event_id:            args.event_id,
        title:               args.title,
        start_time:          t,
        stage_id:            args.stage_id || null,
        duration:            args.duration || 0,
        offset:              0,
        include_in_all_docs: true,
        event_talent_id:     null,
      }),
    }
  );
  process.stdout.write(JSON.stringify(result));
}

main().catch(err => {
  process.stderr.write(JSON.stringify({ error: err.message }) + '\n');
  process.exit(1);
});
