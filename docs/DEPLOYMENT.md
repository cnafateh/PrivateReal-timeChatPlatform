# Deployment and operations

This document explains why each production component is present before listing its settings. For an end-to-end tour of a message, start with the [learning guide](GUIDE.md).

## Deploy with the existing external networks

The repository includes [`compose.production.yml`](../compose.production.yml) for a host that already has `database`, `proxy`, and `my_shared_network`. It runs the published `ghcr.io/cnafateh/chatapp:v1.2.0-rc1` image and Redis, and binds `/srv/chatapp/media` to `/app/media`. Your existing database and reverse proxy remain outside this Compose project. The `.env` must name a reachable `DB_HOST`, database credentials, public host and CSRF origin, and production security settings. A network connection alone does not persist or share files; see [media migration](STORAGE.md) before starting this Compose file.

1. Inspect the old container's `/app/media` and take a database/media backup.
2. Copy media into `/srv/chatapp/media`, set ownership to the container's application UID/GID, and confirm the copy.
3. Put `compose.production.yml` and the production `.env` in the same server directory. Check `docker compose -f compose.production.yml config --quiet`.
4. Start the stack and verify the mount, migrations, two-way chat, uploaded avatars, attachments, and WebSocket upgrade through the public HTTPS proxy.
5. Keep the previous media source until a restore test succeeds. After merging the PR, the `main` workflow publishes the same code as `ghcr.io/cnafateh/chatapp:latest`; change the Compose tag only after that image succeeds.

If the File Browser service needs the files, mount `/srv/chatapp/media` into it read-only. `my_shared_network` is included for network reachability, but does not grant filesystem access.

## Configuration

| Variable | Meaning |
| --- | --- |
| `DJANGO_SECRET_KEY` | Unique random secret; required with `DEBUG=False`. |
| `DEBUG` | Use `False` on a public server. |
| `ALLOWED_HOSTS` | Comma-separated hostnames, without a scheme. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted HTTPS origins, including the scheme. |
| `TIME_ZONE` | Server timezone, default `Asia/Tehran`. The browser displays times in the viewer's timezone. |
| `DB_HOST` | Empty for SQLite; otherwise PostgreSQL hostname. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | PostgreSQL connection settings. |
| `MEDIA_ROOT` | Optional filesystem media root; defaults to `BASE_DIR/media`. Must match the persistent mount. |
| `REDIS_URL` | Full Redis URL, including authentication, database number or `rediss://` when needed. Empty selects a single-process in-memory channel layer. |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS when your proxy correctly forwards the scheme. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Set both to `True` for HTTPS deployments. |
| `SECURE_HSTS_SECONDS` | Enable after confirming HTTPS works reliably. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Optional HSTS settings; enable only when all affected hosts support HTTPS. |

The optional existing `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` startup variables create an administrator only if that username does not already exist. Prefer `createsuperuser` interactively and avoid leaving an administrator password in deployment configuration.

## Production checklist

1. Use PostgreSQL and Redis. An in-memory channel layer cannot share events between workers.
2. Generate a strong secret, disable debug and configure exact hosts/origins.
3. Terminate TLS at a trusted reverse proxy. Daphne must not be directly accessible from the Internet.
4. Preserve WebSocket Upgrade/Connection headers. Trust forwarded scheme/host headers only from your own proxy.
5. With an external TLS proxy in front of the supplied Nginx, configure Nginx's `X-Forwarded-Proto` appropriately for that trusted topology. The example sends `$scheme`, which is `http` inside the local Compose network. Do not enable redirect until the backend receives the real HTTPS scheme; otherwise a redirect loop results.
6. Set the two secure-cookie flags. Limit login/registration attempts and request rates at the public proxy. Add account/storage quotas and malware scanning appropriate to your deployment.
7. Back up PostgreSQL and `/app/media` together. Never add a public Nginx `alias` or Django media URL pattern for private uploads.
8. Run `python manage.py check --deploy` under the production environment.
9. Monitor disk usage, application errors and Redis/database availability.

## Persistent storage

The local Compose stack uses `postgres_data`, `media_data` and `redis_data`. The production Compose example uses the existing external database, a Redis volume, and a host bind mount for media. The image creates `/app/media` before switching to its unprivileged user. Existing bind mounts must be writable by that user. With several application instances, use shared private storage for attachments.

WhiteNoise serves collected application static assets. Authenticated Django views serve message attachments using `FileResponse`; the current implementation does not implement byte-range seeking. Short recordings can play, but seeking behavior varies by browser.

Deleting database messages does not automatically delete physical files. Retaining files avoids deleting storage during a rolled-back transaction; schedule an audited orphan-file cleanup under your retention policy. A server operator must treat backups and orphan files as private content too.

## Upgrade from the original version

1. Back up the database, deployment configuration and any media files.
2. Install the new dependencies or build the new image.
3. Run `python manage.py migrate` before starting the application. Docker startup runs migrations automatically; for multiple replicas run migrations once before rolling out workers.
4. Run `python manage.py collectstatic --noinput`.
5. Restart all application workers and reload open browser tabs.

Migrations `0002`–`0004` add attachment metadata and indexes, canonicalize conversation member order, and merge duplicate reversed pairs while retaining every message. Schema changes and data normalization run in separate transactions so PostgreSQL can validate foreign keys before adding the final constraint. A constraint prevents future reversed duplicates. If legacy self-conversations exist, migration stops and asks an operator to resolve them. Consolidation is not undone by reversing the schema migration: restoring a backup is the way to restore the old pair structure.

Old HTTP chat-creation API calls must use POST with CSRF protection. Logout is now POST-only. WebSocket timestamps now include a full ISO 8601 date and offset. Text messages sent with the original WebSocket payload remain supported.

The supplied Compose file is now a complete local stack. If your server uses external database/proxy networks, port those environment and network settings into a deployment-specific override rather than replacing a working server configuration blindly.

## Troubleshooting

- **Microphone unavailable:** open HTTPS or localhost; grant browser and OS microphone permission.
- **Upload rejected:** each non-empty file must be at most 5 MiB; keep the proxy request-body limit at least 6 MiB.
- **Chat says reconnecting:** check WebSocket proxy headers, `ALLOWED_HOSTS` and Redis connectivity. HTTP history polling recovers missed messages while the page remains open.
- **Messages disappear after recreation:** verify PostgreSQL and media volumes are persistent; do not use ephemeral SQLite inside production containers.
- **Photo downloads instead of displaying:** only verified PNG, JPEG, GIF and WebP receive inline image treatment. Other content is intentionally a download.
- **Static asset errors:** rerun collectstatic with the deployed version and restart workers.


## Profile and public-URL upgrade

Migrations `0005`–`0007` add profile records and populate a distinct random UUID for every existing user profile, conversation and message before enforcing non-null constraints. Existing attachments stay at their current relative storage paths. Back up the database and media, run all migrations and deploy all workers together. Refresh browser clients; old numeric user/chat/file routes are intentionally no longer accepted and old bookmarks return 404. API clients must use the returned UUID URLs. Do not fake the data migrations.

Profiles use optional email for Gravatar fallback, without publishing the address in another user's profile. Uploaded photos take precedence. Phone numbers remain private unless explicitly shared.

For volume inspection, backup, restart/redeploy behavior and an optional host bind mount, see [STORAGE.md](STORAGE.md). No production volume is automatically renamed or replaced by this upgrade.
