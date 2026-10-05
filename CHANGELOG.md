# Changelog

## Unreleased

### Profiles, access URLs and administration

- Replace numeric public routes with random UUIDv4 identifiers for profiles, chats and attachments, including WebSocket endpoints.
- Backfill unique identifiers and profiles while preserving existing messages and file paths.
- Add editable first/last names, private email/phone, optional phone visibility and profile pages.
- Add sanitized uploaded avatars with optional SHA-256 Gravatar fallback.
- Add permission-checked administrator file downloads, photo/audio previews and combined participant filters.
- Remove promotional page copy and simplify authentication and empty states.
- Document media persistence, optional host-directory migration, application usage and the roadmap.

## Messaging upgrade

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
