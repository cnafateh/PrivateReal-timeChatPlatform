# Changelog

## Unreleased

### Added

- Day separators and full timestamp tooltips, with local timezone formatting.
- Private file and photo attachments up to 5 MiB, plus captions.
- Browser voice recording with preview, cancellation and size/duration limits.
- Light/dark themes, responsive conversation layouts and accessible composer controls.
- Read receipts, typing indicators, draft retention, earlier history and reconnection recovery.
- Branded administration with useful filters, counts and read-only message metadata.
- Server, migration, WebSocket and browser regression tests; Python and PostgreSQL/Redis CI jobs.
- Architecture, deployment, testing, contribution and security documentation.

### Fixed

- Missing calendar dates in real-time message payloads.
- History being permanently limited to the latest 100 messages.
- Reversed duplicate conversation pairs and retry-created duplicate messages.
- Inbox queries scaling per conversation.
- Invalid WebSocket payloads crashing the consumer.
- State-changing logout requests using GET.
- Case-insensitive username searches failing when multiple case variants exist.
- Redis URL configuration being ignored.
- Invalid Compose indentation and a non-Nginx file named `nginx.conf`.
- Local environment files being included in Docker build context.

### Upgrade notes

Run migrations and collectstatic, preserve private media storage, and reload browser clients. See `docs/DEPLOYMENT.md` before changing an existing deployment.
