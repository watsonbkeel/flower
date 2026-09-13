#!/bin/sh
set -eu
cd /srv/flower/current
compose() {
    docker compose --project-name flower-prod --env-file /srv/flower/shared/config/production.env --env-file release.env -f docker-compose.yml -f compose.production.yml "$@"
}
# Quiesce writers for a consistent database-plus-files backup.
trap 'compose start api worker' EXIT
compose stop api worker
compose run --rm --no-deps -v /srv/flower/shared/backups:/backup -v /srv/flower/current:/release:ro api python /release/scripts/backup.py backup --directory /backup --uploads /data/uploads --manifest /release/release.json
