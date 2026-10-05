# Security policy

Security fixes target the current main branch. Keep the application and dependencies up to date.

Please report a vulnerability privately using the repository's **Security → Advisories → Report a vulnerability** option when enabled. If private reporting is unavailable, contact the maintainer through their GitHub profile and request a private channel without posting exploit details publicly.

Include affected versions, reproduction steps, impact and a minimal proof of concept with synthetic data. Never upload real credentials, private messages or users' files.

## Security model

Session authentication, CSRF protection and conversation membership checks protect chat actions and attachment access. WebSocket origins must match configured allowed hosts. Administrative access is privileged: server operators can read stored messages and files. This application does not offer end-to-end encryption.

Uploads are untrusted. Generic files always download instead of executing inline. Image verification and audio header checks are not malware scanning. Hosts are responsible for TLS, proxy rate limits, storage quotas, backups, retention and dependency updates. Never expose the media directory directly.


Public URL identifiers are random UUIDv4 values, not access tokens. Membership/permission checks remain mandatory even if a UUID is known. Profiles require login; contact fields have separate visibility rules. Gravatar requests disclose a hash of the user's email to Gravatar and may disclose the viewer's network address. Email hashing is for avatar lookup, not credential protection or guaranteed anonymity. Gravatar can be disabled in profile settings.
