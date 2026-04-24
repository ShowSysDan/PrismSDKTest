'use strict';
/**
 * Bridge script: delete a run-of-show item from Prism.
 *
 * Usage: node ros_delete.js '<json_args>'
 *
 * Required args:
 *   event_id - int
 *   item_id  - int  (Prism-assigned ROS item ID)
 */

const sdk = require('@prismfm/prism-sdk');
const { getPrismSDK } = sdk.default || sdk;

async function main() {
  const args = JSON.parse(process.argv[2] || '{}');
  if (!args.event_id || !args.item_id) {
    throw new Error('event_id and item_id are required');
  }

  const prism = getPrismSDK({});
  let result;
  try {
    result = await prism.callPrismApi(
      `/events/${args.event_id}/run-of-show/${args.item_id}`,
      { method: 'DELETE' }
    );
  } catch (e) {
    // 204 No Content responses may parse as empty — treat as success
    if (e.message && /empty|JSON/i.test(e.message)) {
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
