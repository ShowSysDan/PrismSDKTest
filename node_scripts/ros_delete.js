'use strict';
/**
 * Bridge script: delete a run-of-show item from Prism.
 *
 * Usage: node ros_delete.js '<json_args>'
 *
 * Required args:  event_id, item_id (Prism-assigned ROS item ID)
 */

const { getPrismAndXsrf } = require('./prism_write_auth');

async function main() {
  const args = JSON.parse(process.argv[2] || '{}');
  if (!args.event_id || !args.item_id) {
    throw new Error('event_id and item_id are required');
  }

  const { prism, xsrfToken } = await getPrismAndXsrf();

  let result;
  try {
    result = await prism.callPrismApi(
      `/events/${args.event_id}/run-of-show/${args.item_id}`,
      {
        method: 'DELETE',
        headers: {
          ...(xsrfToken ? { 'x-xsrf-token': xsrfToken } : {}),
        },
      }
    );
  } catch (e) {
    // 204 No Content may surface as an empty-body JSON parse error
    if (e.message && /empty|JSON|token/i.test(e.message)) {
      result = null;
    } else {
      throw e;
    }
  }
  process.stdout.write(JSON.stringify(result || { deleted: true }));
}

main().catch(err => {
  process.stderr.write(JSON.stringify({ error: err.message }) + '\n');
  process.exit(1);
});
