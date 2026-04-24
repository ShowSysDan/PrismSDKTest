'use strict';
/**
 * Bridge script: fetch run of show items from Prism FM API.
 *
 * Usage: node get_run_of_show.js '<json_args>'
 *
 * JSON args:
 *   startDate     - YYYY-MM-DD  [Required]
 *   endDate       - YYYY-MM-DD  [Required]
 *   stageIds      - number[]    (optional)
 *   venueIds      - number[]    (optional)
 *   talentAgentIds- number[]    (optional)
 *   eventTagIds   - number[]    (optional)
 *   excludeFrom   - YYYY-MM-DD  (optional)
 *   excludeUntil  - YYYY-MM-DD  (optional)
 *
 * Outputs JSON array of RunOfShowItem objects to stdout.
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

if (!args.startDate || !args.endDate) {
  process.stderr.write(
    JSON.stringify({ error: 'startDate and endDate are required', name: 'ValidationError' }) + '\n'
  );
  process.exit(1);
}

async function main() {
  const prism = getPrismSDK({});
  const items = await prism.getRunOfShow(args);
  process.stdout.write(JSON.stringify(items));
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
