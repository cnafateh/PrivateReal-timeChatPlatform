# Testing

## Server suite

```sh
python manage.py test --settings=chatapp_project.test_settings
python manage.py makemigrations --check --dry-run --settings=chatapp_project.test_settings
python manage.py check --settings=chatapp_project.test_settings
```

The test settings isolate database and Redis settings from your `.env`, use fast test-only password hashes and disable HTTPS redirects for the local test client. Never run a deployed service with test settings.

Coverage includes authentication, POST-only logout and CSRF enforcement; canonical conversation pairs; authorization for history, sends and private downloads; 5 MiB boundaries; actual-image detection and spoofed files; audio container handling; duplicate-send recovery; history cursors; receipt ownership; safe JSON embedding; query counts; admin pages; WebSocket payload validation and origins; and preservation of legacy messages during migration.

To use PostgreSQL/Redis in tests, provide `TEST_DB_HOST=localhost` and `TEST_REDIS_URL=redis://localhost:6379/0`. The dedicated PostgreSQL service must accept username/password `postgres` and provide a `pulse_test` database. Tests create and destroy their own test database.

## Browser suite

Install the development requirements and Chromium, then set `RUN_BROWSER_TESTS=1` and run:

```sh
python manage.py test browser_tests --settings=chatapp_project.test_settings
```

The browser suite checks day grouping, text/file submission, theme persistence, mobile overflow, oversized file feedback and microphone-denial behavior. Its test server exercises HTTP fallback; separate Channels tests exercise socket delivery. It uses isolated test accounts and does not contact an external deployment.

## Manual release checks

- Open two accounts in separate profiles. Check live messages, typing and read receipts.
- Send a photo, PDF and file exactly 5 MiB; reject one byte more.
- Record and preview audio in Chromium and Safari on HTTPS. Stop, remove and rerecord. Deny microphone permission and verify the message remains usable.
- Send messages on both sides of local midnight. Check Today/Yesterday labels and older dates.
- Load several earlier-history pages. Scroll up while another account sends; the viewport should stay put until you choose New messages.
- Disconnect/reconnect networking and retry a failed upload. Confirm no duplicate message appears.
- Check desktop and mobile in both themes, keyboard focus, Persian/Arabic text, multiline text and browser zoom.
- Verify a third account and a logged-out browser cannot download a copied attachment URL.

Browser codecs, hardware microphone capture and public proxy configuration need these real-device checks in addition to CI.


## Profile and identifier regression coverage

The suite checks UUID uniqueness/backfills and rejection of numeric routes, owner-only profile editing, hidden contact details, optional phone sharing, Gravatar normalization/opt-out, avatar validation/resizing/removal, administrator file permissions and combined participant filters. Browser tests follow the profile links, upload an avatar and edit names/phone on desktop and mobile. No test contacts a real user's Gravatar account.
