# Security review

This review covers the Django HTTP and WebSocket entry points, file handling, Android bridge, administrator access, and deployment defaults. It describes concrete code and configuration changes; it is not a claim that the system is free of vulnerabilities.

## Findings addressed in this release

| Area | Finding | Change |
| --- | --- | --- |
| Group uploads | The streaming 5 MiB upload limit middleware covered private chats and profiles but omitted `/api/groups/`. A large group upload could reach the view before the file-size check. | Apply the same pre-read request cap and streaming handler to group routes; add a regression test. |
| Stale WebSockets | An already-connected inbox socket could continue receiving update events after its account was disabled. Private chat checks did not explicitly reject an inactive current user. | Recheck active status before inbox delivery and heartbeat, and require active participants for private chat events and legacy WebSocket sends. |
| Login guessing | The login endpoint had no application-level attempt cap. | Limit failed attempts for each normalized account name to ten in a 15-minute Redis window. The Redis key is derived from a hash of the account name and server secret. Successful login clears the counter. |
| Development mode | Missing `DEBUG` configuration selected development mode. | Default to `False`, so production startup needs a configured secret. The example `.env` still explicitly enables development mode for local use. |
| Android microphone | Browser media capture inside WebView could fail after permission was granted. | Record through Android's microphone API in the native shell, with explicit runtime permission and temporary private cache storage. |
| Avatar delivery | Every authenticated avatar response disabled caching, leading to repeated downloads. | Give uploads versioned URLs and private device caching. A changed file gets a new URL; unversioned requests must revalidate. |
| Python dependencies | The pinned Django, Daphne, Pillow, and python-dotenv versions had published advisories. | Upgrade to patched releases and add a `pip-audit` check to CI. |
| Image publishing | The Docker publish workflow also allowed pushes to an obsolete review branch. | Publish the production image only from `main` after its required tests pass. |

The dependency audit still reports [GHSA-8pqf-f4m5-798g](https://github.com/advisories/GHSA-8pqf-f4m5-798g) in Twisted, a Daphne transitive dependency. The advisory affects Twisted's IMAP wildcard parser; this application does not start an IMAP server or call that parser. No patched Twisted release is listed as of this review, so CI explicitly ignores this one advisory while checking every other dependency. Revisit the exception when a patched Twisted release is available or the application's use of Twisted changes.

## Existing controls checked

Conversation reads, writes, media downloads, and group WebSockets check current membership. Public paths use random UUIDs, not internal numeric identifiers. HTTP mutations use POST and Django CSRF middleware; WebSocket handshakes use the allowed-host origin validator and session authentication. Uploaded raster photos are decoded and re-encoded; private files are stored outside static assets and generic files download with `nosniff` and a sandbox policy. The Android bridge accepts messages only from the configured HTTPS host and its main frame, and TLS errors are rejected. Superuser monitoring requires an active superuser session and disables response caching.

## Operations and remaining work

Login throttling and HTTP counters require Redis; if it is unavailable, login remains available and the throttle cannot be enforced. Keep a proxy-level request limit, particularly for registration and unknown account names. Do not expose Daphne or the private media directory directly. Set a strong `DJANGO_SECRET_KEY`, `DEBUG=False`, exact `ALLOWED_HOSTS` and HTTPS CSRF origins. Configure secure cookies and HSTS after verifying the trusted TLS proxy and its forwarded-protocol header. Run `python manage.py check --deploy` under the **production** environment, not the local test settings.

Stored files are not malware-scanned. Deleting a database row does not currently delete every orphaned physical file. There is no end-to-end encryption, per-user upload quota, external alerting, or security event feed. The follow-up issue tracks those operational improvements. Back up the database and private media together and test recovery. Never paste secrets, private message contents, or raw production logs into a public issue.
