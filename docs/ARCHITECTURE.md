# Architecture

Django handles authentication, page rendering, history, attachment uploads and downloads. Channels delivers conversation events over authenticated WebSockets. Redis shares those events between workers. PostgreSQL or SQLite stores messages and conversation membership.

## Message flow

1. The page receives the latest 50 messages in an escaped `json_script` payload.
2. Text, captions and optional files are submitted over HTTP with CSRF protection and a client UUID.
3. The server checks membership, validates the payload, stores the message and broadcasts an event.
4. The sender receives the saved message in the HTTP response, even when real-time delivery is unavailable.
5. Clients deduplicate by message ID, fetch missed messages on reconnect and poll every 15 seconds while visible.
6. A visible conversation at its latest messages acknowledges a read cursor. The server updates only messages received by that user, up to that ID.

Text drafts live in session storage, scoped to the user, conversation and browser tab. File selections and recordings are not persisted. A failed request keeps its UUID and payload for retry; a changed payload receives a new UUID.

## Data model

- `PrivateChat`: a random public UUID, two ordered user foreign keys, one unique pair and a creation time.
- `Message`: a random public UUID, sender, receiver, content, timestamp, read flag, kind, optional file and metadata, optional client UUID and optional reply reference to a message in the same conversation.
- `Profile`: a one-to-one user record with a random public UUID, uploaded avatar, phone, contact/avatar preferences and last-seen time. Names and email remain on Django User.
- Indexes cover conversation cursor queries and recipient unread lookups.
- The sender/client UUID pair is unique. A UUID reused in another conversation returns HTTP 409.

Cursor pagination orders by message ID for deterministic delivery and gap recovery. Timestamps are timezone-aware ISO 8601 strings; grouping happens in the browser's timezone. The earlier-history control loads 50 messages per page.

## HTTP endpoints

All chat endpoints require a session. URL path identifiers are random UUIDv4 values generated with Python `uuid.uuid4`; they are not hashes of sequential database IDs. Numeric legacy routes return 404. Database primary keys and history/read cursors remain internal integer ordering keys, not authorization tokens. State-changing requests require POST and a CSRF token.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Inbox |
| GET | `/search/?q=username` | Exact, case-insensitive username lookup |
| GET | `/chat/<profile_uuid>/` | Open a conversation |
| POST | `/api/chat/<profile_uuid>/` | Resolve/create a conversation |
| GET | `/api/chats/<chat_uuid>/messages/` | Latest page of history |
| GET | `/api/chats/<chat_uuid>/messages/?before=<id>` | Earlier page |
| GET | `/api/chats/<chat_uuid>/messages/?after=<id>` | Catch-up page, ascending |
| POST | `/api/chats/<chat_uuid>/send/` | Multipart `message`, `client_id`, optional `file`, optional `kind=voice`, optional `reply_to=<message_id>` |
| POST | `/api/chats/<chat_uuid>/read/` | Acknowledge `through=<message_id>` |
| GET | `/api/mobile/unread/` | Latest unread messages for the signed-in user, used by Android notifications |
| GET | `/api/presence/<profile_uuid>/` | Online state and last-seen time for an active user |
| POST | `/api/presence/heartbeat/` | CSRF-protected fallback that updates the current user's last-seen time |
| GET | `/attachments/<message_uuid>/` | Member-only file or inline media |
| GET | `/attachments/<message_uuid>/?download=1` | Force file download |
| GET/POST | `/profile/edit/` | Edit only the signed-in user’s profile |
| GET | `/people/<profile_uuid>/` | View an active user’s profile |
| GET | `/people/<profile_uuid>/avatar/` | Authenticated uploaded photo |
| POST | `/logout/` | End the session |

History returns `{messages: [...], has_more: boolean}`. Invalid payloads return JSON errors with HTTP 400; oversized request bodies return 413; outsiders receive 404. Unauthenticated sessions redirect to login, which the browser client recognizes as an expired session.

## WebSocket

Connect to `/ws/chat/private/<chat_uuid>/`. Session authentication and the allowed-host origin validator protect the handshake. Nonmembers are rejected with code 4403.

Events are `message`, `read` and `typing`. Send `{type: "typing"}` to announce typing; server-side throttling limits these events to one every two seconds per connection. The legacy `{message: "text"}` command still persists and broadcasts text, but HTTP sending provides retry-safe UUIDs and attachment support.

Every authenticated page also connects to `/ws/inbox/`. WebSocket and HTTP heartbeats update the profile's last-seen time; a profile counts as online for 75 seconds after the latest heartbeat. The HTTP path keeps presence current when a proxy drops WebSockets. A dropped connection eventually becomes offline without requiring a reliable disconnect event. The Android WebView forwards inbox checks to native notification handling while visible; WorkManager uses the saved session cookie for periodic background checks.

Message payloads contain `id`, `sender_id`, `sender`, `message`, `timestamp`, `kind`, `is_read`, `client_id`, `name`, `size`, a `reply_to` summary when present and a protected `attachment_url` when present. Reply targets are accepted only from the same conversation. User text is rendered with DOM `textContent`, never interpolated into HTML.

## Upload trust boundary

A streaming upload handler stops individual files beyond 5 MiB; the view independently verifies non-empty size. Nginx limits the full request to 6 MiB. Files receive random storage names, and original names are metadata only. Pillow verifies raster image contents. Voice containers are identified by their headers. General files, including HTML and SVG, are binary downloads with `nosniff`; private responses use `no-store` and a restrictive sandbox CSP.

This does not provide malware scanning, end-to-end encryption, full media transcoding or per-user storage quotas. Production operators should apply their own retention and abuse controls.


## Profiles and avatar selection

User creation signals create a profile; migration backfills existing users. Uploaded photos take priority. Photos are decoded, limited to 20 megapixels, resized to at most 512×512 and rewritten as PNG without source metadata. If no upload exists and Gravatar is enabled, an optional email is trimmed, lowercased and SHA-256 hashed using Python `hashlib`. The browser loads `https://gravatar.com/avatar/<hash>?s=160&d=404&r=g`. Missing/unavailable images fall back to the local initial. No API key or automatic import of third-party profile names is involved.

Email is private; phone is private unless the owner explicitly enables visibility. Phone formatting validation does not prove ownership. Names and photos are visible to authenticated users. Gravatar can observe avatar requests and email hashes are not anonymous secrets. Users may disable Gravatar. See the [official avatar API](https://docs.gravatar.com/sdk/images/).

## Administrator access

Public attachment views continue to require conversation membership, including for administrators. The dedicated admin route additionally checks the message model's view/change permission and provides image/audio previews or download-only generic files. This separates operator access from participant access. Filters combine an exact participant username (either direction), sender, recipient, kind, attachment presence, read state and date. Admin URLs may use internal IDs inside Django's permission-protected interface.
