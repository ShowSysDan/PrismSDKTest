'use strict';
/**
 * Bridge script: fetch venues from Prism FM API.
 *
 * Usage: node get_venues.js '<json_args>'
 *
 * JSON args (all optional):
 *   includeInactive - boolean, include inactive venues (default: false)
 *
 * Outputs JSON array of venue objects to stdout.
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

async function main() {
  const prism = getPrismSDK({});
  const venues = await prism.getVenues(args);
  process.stdout.write(JSON.stringify(venues));
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
