#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/.agents/skills"
mkdir -p "$DEST"
for d in "$ROOT"/.agents/skills/*; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  ln -sfn "$d" "$DEST/flower-$name"
done
printf 'Linked project skills into %s\n' "$DEST"
