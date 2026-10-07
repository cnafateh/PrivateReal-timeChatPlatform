# Pulse

A self-hosted, real-time private messenger built with Django and Channels.

[![Tests and build](https://github.com/cnafateh/PrivateReal-timeChatPlatform/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/cnafateh/PrivateReal-timeChatPlatform/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Features

- Public UUIDv4 URLs with member-only chat and attachment access.
- Editable names, private email/phone, uploaded profile photos and optional Gravatar fallback.
- User profile pages, with phone visibility controlled by the owner.
- One-to-one conversations with real-time updates and unread counts.
- Telegram-style day separators: Today, Yesterday, and full dates. Times follow the reader's device timezone; hover a time to see its complete date.
- Photos, documents and other files, up to **5 MiB (5,242,880 bytes)** each, with optional captions.
- Record, preview, remove and send voice messages. Recording stops at five minutes or near the upload limit.
- Persistent light/dark theme, with the operating-system preference as the default.
- Read receipts, typing indicators, earlier-message pagination and automatic reconnection.
- Reply to messages with a quoted preview in the conversation.
- Long-press a message to reply or copy its text; see online and last-seen status for other users.
- Recovery of missed messages through periodic history synchronization; repeat requests do not duplicate messages.
- Per-conversation text drafts in the current browser tab, multiline text, bidirectional message text and responsive layouts.
- Administration with image/audio previews, protected file downloads and combined participant, sender, recipient, attachment, type, date and read-state filters.

## Run locally

Requires Python **3.12+**. SQLite and a single-process channel layer are used when database and Redis addresses are absent.

```sh
git clone https://github.com/cnafateh/PrivateReal-timeChatPlatform.git
cd PrivateReal-timeChatPlatform
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# PowerShell: Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://localhost:8000>. Register a second account in another browser profile, search for its username and start a conversation. The administration panel is at `/admin/`.

Local `.env` files are ignored by Git and Docker. Set your own `DJANGO_SECRET_KEY`. Never reuse the example credentials on a public deployment.

## Docker

```sh
cp .env.example .env
# Set DJANGO_SECRET_KEY and DB_PASSWORD in .env.
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Open <http://localhost:8080>. Compose starts Django/Daphne, PostgreSQL, Redis and Nginx, with persistent volumes for database records and uploaded files. Nginx accepts request bodies up to 6 MiB to leave room for multipart framing; each attachment is limited to 5 MiB by the application.

For public hosting and upgrades, follow [deployment instructions](docs/DEPLOYMENT.md). The provided Compose file binds to localhost; configure your trusted HTTPS proxy before exposing the service.

For a server with external database and proxy networks, use [the production Compose example](compose.production.yml) after following the [media migration guide](docs/STORAGE.md). It keeps uploaded avatars and attachments in `/srv/chatapp/media` on the host. The review image is `ghcr.io/cnafateh/chatapp:v1.2.0-rc1`; `latest` is published from `main` after merge.

## Tests

```sh
pip install -r requirements-dev.txt
python manage.py test --settings=chatapp_project.test_settings
coverage run --source=chat --omit='chat/migrations/*,chat/test*' manage.py test --settings=chatapp_project.test_settings
coverage report
```

Browser tests are opt-in:

```sh
python -m playwright install chromium
RUN_BROWSER_TESTS=1 python manage.py test browser_tests --settings=chatapp_project.test_settings
# PowerShell: $env:RUN_BROWSER_TESTS='1'; python manage.py test browser_tests --settings=chatapp_project.test_settings
```

GitHub Actions runs server tests on Python 3.12 and 3.13, PostgreSQL/Redis integration tests, Chromium interface tests, migration checks, JavaScript syntax checks and static asset collection. The Docker publishing job waits for all test jobs to pass.

Tests use a separate database and temporary uploads. They do not modify your development conversations. See [testing details](docs/TESTING.md).

## Privacy and limitations

Only conversation members can retrieve attachments. Media files are never published as public static files. General files download as binary attachments; validated raster images and supported audio containers can be viewed inline.

Messages and files are stored on your server. **This is not end-to-end encryption**: authorized server operators can access stored content. File downloads are not malware-scanned. Audio container detection does not validate every codec or guarantee playback in every browser. Mobile Safari and Chromium may select different recording formats.

Voice recording needs microphone permission and HTTPS, except on localhost. File selection remains available if recording is unsupported. The Android app checks for messages periodically while closed; instant push delivery is not available without a push provider.

## Documentation

- [Learning guide: application flow and architecture](docs/GUIDE.md)
- [Android app build, installation and notifications](docs/ANDROID.md)
- [Media persistence, host directories and backups](docs/STORAGE.md)
- [Deployment, configuration and upgrades](docs/DEPLOYMENT.md)
- [Architecture and HTTP/WebSocket protocol](docs/ARCHITECTURE.md)
- [Tests and manual verification](docs/TESTING.md)
- [Contributing](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Release notes](CHANGELOG.md)

## Contributing and license

Bug reports and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

Released under the [MIT License](LICENSE).


## Roadmap

The following are planned or possible improvements, not features implemented today:

- Verified email and phone ownership; password recovery and two-factor authentication.
- Blocking/reporting users, moderation tools, account quotas and per-account rate limiting.
- Full-text message search, replies, message editing/deletion with an explicit retention policy.
- Firebase Cloud Messaging or another push provider for immediate background notifications, plus per-conversation notification preferences.
- Group conversations with role-based membership.
- Private object storage, malware scanning and audited orphan-file cleanup.
- Range requests and transcoding for broader voice playback/seek support.
- Account export/deletion, configurable profile visibility and an audit log for administrator file access.

Contributions should include authorization tests and a migration/deployment plan where appropriate.
