# Operational monitoring

Open `/monitor/` as an active superuser. The page refreshes every minute and sends `Cache-Control: no-store`. Ordinary users, staff users without superuser status, and signed-out visitors receive HTTP 403. A link is available from the admin header.

## What the first version measures

The dashboard checks a database query, Redis connectivity, and whether the configured private media directory accepts a small temporary file. It reports free space on the media filesystem. Application totals cover users, private chats, and groups; the last 24 hours include new users and messages. Redis holds 24 hourly HTTP buckets with request, 4xx, 5xx, and average response-time counts. A bounded list shows the last 20 server errors by time, named Django route, and status.

`RequestMetricsMiddleware` records a response after Django handles it. It sends a small Redis pipeline and expires keys after 48 hours. The monitor endpoint excludes its own requests. A short retry delay avoids adding Redis connection time to every request during an outage. No message body, full URL, query string, account name, cookie, IP address, or uploaded file name is written to these metrics. The dashboard reads counts directly; it does not provide a public metrics endpoint.

## How to read it

- **Database unavailable:** check PostgreSQL connectivity and credentials, then inspect application logs. A successful connection check does not validate every query or migration.
- **Redis unavailable:** real-time chat and monitoring counters may be delayed or absent. HTTP messaging can still persist to the database; clients recover missed events through history synchronization.
- **Media storage not writable:** verify the host bind mount, ownership, free space and container user. A writable directory check does not prove that every existing file is readable.
- **5xx rising:** inspect the recent named routes and application logs. The dashboard intentionally does not store stack traces or user data.
- **Average response time rising:** this is server-side HTTP time, not Android or browser rendering time. Check database and Redis health first.

Counters start when this release is deployed and are not backfilled. They disappear after Redis is flushed or 48 hours pass. WebSocket events and background Android jobs are not included in HTTP buckets; database message counts include messages regardless of transport. This page is a first operational view, not a replacement for external uptime checks, backups, structured logs, alert delivery, or full tracing. For more than one server, point every instance at the same Redis and private media storage.

Check the page after deployment, then run a harmless chat message and confirm the current hour and message count change. Test the media probe using the same container user that runs the web process. The monitoring Redis keys use the `pulse:monitor:v1` prefix and are independent of Channels keys.
