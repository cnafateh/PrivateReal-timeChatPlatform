# Private media storage and backups

## Production host directory

The supplied [`compose.production.yml`](../compose.production.yml) binds **`/srv/chatapp/media` on the host** to **`/app/media` in the web container**. Django's `MEDIA_ROOT` stays `/app/media`. Attachments and uploaded avatars then survive restarts and image redeploys as long as the host directory remains. The Compose file uses the existing external `database`, `proxy`, and `my_shared_network` networks; Redis remains on its internal network. Configure the database host and credentials in the production `.env`.

A Docker network does not share files. To inspect uploads in an existing File Browser container, give that container a separate read-only mount of `/srv/chatapp/media`, for example `/srv/chatapp/media:/srv/pulse-media:ro`. Restrict File Browser access and never expose this private directory as a public static route: Django's download view checks conversation membership.

### Migrate before enabling the bind mount

Run the following on the server while the old `chatapp` container still exists. First back up the database and current media, and confirm the source contains the expected `avatars/` and `attachments/` files.

```sh
docker inspect chatapp --format '{{json .Mounts}}'
docker exec chatapp sh -c 'find /app/media -maxdepth 2 -type f | head'
PULSE_UID=$(docker exec chatapp id -u)
PULSE_GID=$(docker exec chatapp id -g)
docker stop chatapp
sudo install -d -m 0750 /srv/chatapp/media
docker cp chatapp:/app/media/. /srv/chatapp/media/
sudo chown -R "$PULSE_UID:$PULSE_GID" /srv/chatapp/media
```

Check copied file counts and a sample avatar against the source. If the old container has an empty `/app/media`, inspect earlier containers, old named volumes, and backups before proceeding. A database row cannot recreate missing image bytes. Mounting an empty host directory hides files in the container or volume; it does not migrate them.

```sh
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml up -d
docker inspect chatapp --format '{{json .Mounts}}'
```

The final inspection must show `/srv/chatapp/media` as source and `/app/media` as destination. Verify an existing avatar and attachment through the app before removing the old container or volume. Retain both database and media backups.

## Where the files live

The repository's local-development Compose configuration mounts the Docker named volume `media_data` at **`/app/media`**. The production example above uses a host bind mount at the same container path. Django's default `MEDIA_ROOT` resolves to that path inside the image. Message files live under `attachments/<internal-chat-id>/<random-name>`; uploaded profile photos live under `avatars/<profile-uuid>/<random-name>.png`. The database stores storage-relative paths and metadata, not the file contents.

A named volume is already stored on the Docker host, outside the container's disposable writable layer. A host bind mount gives an explicit host path; it is not required merely to survive restarts.

| Operation | With the existing media volume mounted |
| --- | --- |
| Restart web/container/host | Files remain. |
| Rebuild image or recreate web with the same volume | Files remain. |
| `docker compose down`, without `--volumes` | Named media volume remains. |
| Redeploy under a different Compose project/volume name | A new empty volume may be attached; the old files usually remain in the old volume. |
| `docker compose down --volumes` / explicit volume deletion | Files in that volume are deleted. |
| Run without a mount, then remove the container | Files in the container writable layer are lost. |
| Move to another host | Copy/restore both database and media; local volumes do not move automatically. |

These statements describe this repository. Verify the actual server configuration before assuming a deployed container uses the same mount.

## Inspect the deployed mount

Run on the Docker host, from the deployed Compose project directory:

```sh
docker inspect "$(docker compose ps -q web)" --format '{{json .Mounts}}'
docker compose exec -T web python manage.py shell -c "from django.conf import settings; print(settings.MEDIA_ROOT)"
```

Look for a mount with `Destination` equal to `/app/media`. For `Type: volume`, copy the exact `Name` from the output and run:

```sh
docker volume inspect ACTUAL_VOLUME_NAME --format '{{.Mountpoint}}'
```

A rootful Linux Docker host often uses `/var/lib/docker/volumes/<name>/_data`, but rootless Docker, custom data roots and Docker Desktop differ. Use inspection rather than assuming that path. Docker Desktop volumes live in its Linux VM.

## Optional explicit host directory

The default named volume remains unchanged to avoid hiding existing uploads. To use `/srv/pulse/media`, the repository provides `compose.media-bind.example.yml` as an optional override. **Copy existing files before enabling it.** Mounting an empty host directory over `/app/media` hides the volume's contents; it does not migrate them.

For a Linux Docker host, during a maintenance window:

```sh
# Save the current runtime UID/GID while the service is running.
PULSE_UID=$(docker compose exec -T web id -u)
PULSE_GID=$(docker compose exec -T web id -g)

# Stop writes, but keep the stopped container for docker cp.
docker compose stop web
sudo install -d -m 0750 /srv/pulse/media
sudo docker compose cp web:/app/media/. /srv/pulse/media/
sudo chown -R "$PULSE_UID:$PULSE_GID" /srv/pulse/media
```

Confirm the resolved host target is the intended `/srv/pulse/media` before changing ownership. Back up the original database and volume first. Add `PULSE_MEDIA_DIR=/srv/pulse/media` to your deployment `.env`, then:

```sh
docker compose -f docker-compose.yml -f compose.media-bind.example.yml up -d
```

Use both Compose files on subsequent redeploys. Verify an existing message attachment and profile photo through the application. Keep the original volume until the copy and a restore test are verified. Do not use `down --volumes` during this migration. If the container was already replaced without a mount, stop writes and recover the prior container or backup before proceeding.

The override refuses to create a missing source directory automatically. The process inside the container needs read/write access to the directory. Keep `MEDIA_ROOT=/app/media` inside the container for the supplied mount; only set a custom `MEDIA_ROOT` when deploying with a matching mount or outside Docker.

## Consistent backup

Back up database and media together. For the supplied PostgreSQL stack:

```sh
mkdir -p backup/media
docker compose stop web
docker compose exec -T db pg_dump -U chatapp -d chatapp -Fc > backup/pulse-db.dump
docker compose cp web:/app/media/. backup/media/
docker compose start web
```

Adapt service names, credentials and override flags to the deployment. Store encrypted backups off-host and test restoration in an isolated stack. Database-only backups cannot recover attachment bytes; media-only backups cannot recover membership or message metadata.

Restore the database dump to an isolated database, copy the media tree into the mounted media storage with the correct ownership, and run migrations before testing. Reuse relative paths exactly. Never turn the private media folder into a public static directory for convenience.

## Access and retention

Django serves message files only to conversation members. A separate admin endpoint permits staff with `view_message` or `change_message`; setting `is_staff` alone does not grant file access. Profile photos are visible to authenticated users while the profile is active. Gravatar images are hosted externally and are not stored in this volume.

Replacing/removing a profile photo deletes the previous stored photo after a successful database commit. Deleting message rows does not automatically delete their files; an audited retention/orphan cleanup remains an operator responsibility. Files and backups contain private information.
