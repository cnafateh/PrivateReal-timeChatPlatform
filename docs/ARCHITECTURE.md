# Architecture

Django handles authentication, page rendering, history, attachment uploads and downloads. Channels delivers conversation events over authenticated WebSockets. Redis shares those events between workers. PostgreSQL or SQLite stores messages and conversation membership.

## Message flow

1. The page receives the latest 50 messages in an escaped `json_script` payload.
2. Text, captions and optional files are submitted over HTTP with CSRF protection and a client UUID.
3. The server checks membership, validates the payload, stores the message and broadcasts an event.
4. The sender receives the saved message in the HTTP response, even when real-time delivery is unavailable.
5. Clients deduplicate by message ID, fetch missed messages on reconnect and poll every 15 seconds while visible.
6. A visible conversation at its latest messages acknowledges a read cursor. The server updates only messages received by that user, up to that ID.

Text drafts live in session storage, scoped to the conversation and browser tab. File selections and recordings are not persisted. A failed request keeps its UUID and payload for retry; a changed payload receives a new UUID.

## Data model

- `PrivateChat`: two ordered user foreign keys, one unique pair and a creation time.
- `Message`: sender, receiver, content, timestamp, read flag, kind, optional file and metadata, optional client UUID.
- Indexes cover conversation cursor queries and recipient unread lookups.
- The sender/client UUID pair is unique. A UUID reused in another conversation returns HTTP 409.

Cursor pagination orders by message ID for deterministic delivery and gap recovery. Timestamps are timezone-aware ISO 8601 strings; grouping happens in the browser's timezone. The earlier-history control loads 50 messages per page.

## HTTP endpoints

All chat endpoints require a session. State-changing requests require POST and a CSRF token.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Inbox |
| GET | `/search/?q=username` | Exact, case-insensitive username lookup |
| GET | `/chat/<user_id>/` | Open a conversation |
| POST | `/api/chat/<user_id>/` | Resolve/create a conversation |
| GET | `/api/chats/<chat_id>/messages/` | Latest page of history |
| GET | `/api/chats/<chat_id>/messages/?before=<id>` | Earlier page |
| GET | `/api/chats/<chat_id>/messages/?after=<id>` | Catch-up page, ascending |
| POST | `/api/chats/<chat_id>/send/` | Multipart `message`, `client_id`, optional `file`, optional `kind=voice` |
| POST | `/api/chats/<chat_id>/read/` | Acknowledge `through=<message_id>` |
| GET | `/attachments/<message_id>/` | Member-only file or inline media |
| GET | `/attachments/<message_id>/?download=1` | Force file download |
| POST | `/logout/` | End the session |

History returns `{messages: [...], has_more: boolean}`. Invalid payloads return JSON errors with HTTP 400; oversized request bodies return 413; outsiders receive 404. Unauthenticated sessions redirect to login, which the browser client recognizes as an expired session.

## WebSocket

Connect to `/ws/chat/private/<chat_id>/`. Session authentication and the allowed-host origin validator protect the handshake. Nonmembers are rejected with code 4403.

Events are `message`, `read` and `typing`. Send `{type: "typing"}` to announce typing; server-side throttling limits these events to one every two seconds per connection. The legacy `{message: "text"}` command still persists and broadcasts text, but HTTP sending provides retry-safe UUIDs and attachment support.

Message payloads contain `id`, `sender_id`, `sender`, `message`, `timestamp`, `kind`, `is_read`, `client_id`, `name`, `size` and a protected `attachment_url` when present. User text is rendered with DOM `textContent`, never interpolated into HTML.

## Upload trust boundary

A streaming upload handler stops individual files beyond 5 MiB; the view independently verifies non-empty size. Nginx limits the full request to 6 MiB. Files receive random storage names, and original names are metadata only. Pillow verifies raster image contents. Voice containers are identified by their headers. General files, including HTML and SVG, are binary downloads with `nosniff`; private responses use `no-store` and a restrictive sandbox CSP.

This does not provide malware scanning, end-to-end encryption, full media transcoding or per-user storage quotas. Production operators should apply their own retention and abuse controls.
