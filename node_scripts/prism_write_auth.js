'use strict';
/**
 * Shared helper for Prism write operations.
 *
 * callPrismApi routes to app.prism.fm and adds the Bearer token
 * automatically, but Laravel's CSRF middleware also requires an
 * x-xsrf-token header on POST / PUT / DELETE.
 *
 * This module:
 *   1. Temporarily wraps globalThis.fetch to capture the Bearer JWT
 *      the SDK generates (it is opaque – not the SDK token format).
 *   2. Uses that JWT to GET /sanctum/csrf-cookie, which sets the
 *      XSRF-TOKEN cookie and returns it in the response headers.
 *   3. Returns the prism SDK instance + the decoded XSRF token value,
 *      ready to be passed as  { 'x-xsrf-token': xsrfToken }.
 */

const sdk = require('@prismfm/prism-sdk');
const { getPrismSDK } = sdk.default || sdk;

async function getPrismAndXsrf() {
  const origFetch = globalThis.fetch;
  let capturedAuth = null;

  // Wrap fetch to capture the first Bearer token headed to prism.fm
  globalThis.fetch = async function (url, opts) {
    if (!capturedAuth && opts && String(url).includes('prism.fm')) {
      const h = opts.headers || {};
      const auth =
        typeof h.get === 'function'
          ? h.get('authorization')
          : h['authorization'] || h['Authorization'];
      if (auth && String(auth).startsWith('Bearer ')) capturedAuth = auth;
    }
    return origFetch.apply(this, arguments);
  };

  const prism = getPrismSDK({});

  // A lightweight GET to trigger token init + capture the Bearer JWT.
  // Failures are expected (403 scope issues, etc.) — we only need the header.
  try { await prism.getCurrentUser(); } catch (_) {}

  globalThis.fetch = origFetch; // restore before making any further calls

  // Exchange the Bearer token for a fresh XSRF cookie
  let xsrfToken = null;
  if (capturedAuth) {
    try {
      const r = await origFetch('https://app.prism.fm/sanctum/csrf-cookie', {
        headers: {
          authorization:   capturedAuth,
          accept:          'application/json',
          'app-version':   '*',
        },
      });
      // node-fetch / undici may merge multiple Set-Cookie headers with commas
      const cookie = r.headers.get('set-cookie') || '';
      const m = cookie.match(/XSRF-TOKEN=([^;,\s]+)/i);
      if (m) xsrfToken = decodeURIComponent(m[1]);
    } catch (_) {}
  }

  if (!xsrfToken) {
    process.stderr.write(
      '[prism_write_auth] Warning: could not obtain XSRF token — ' +
      'write request may be rejected with a 419 CSRF error.\n'
    );
  }

  return { prism, xsrfToken };
}

module.exports = { getPrismAndXsrf };
