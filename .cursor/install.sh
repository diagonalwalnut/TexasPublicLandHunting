#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Texas Public Land Hunting.
# Runs after the repository is checked out. Safe to run repeatedly.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# System dependency: PHP CLI + SQLite drive the accounts API (sign-up/sign-in,
# saved units). Argon2id password hashing ships with PHP 8.3. The map and hunt
# report run without it, but the auth test and account flows need it.
if ! command -v php >/dev/null 2>&1 || ! php -m | grep -qix 'sqlite3'; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    php-cli php-sqlite3
fi

# Python data pipeline (scripts/*.py) and the auth/data/methods tests. The app
# itself serves the already-committed data under web/public/data/, so this is
# only needed to regenerate data or run the Python tests.
python3 -m pip install --break-system-packages -r requirements.txt

# Frontend dependencies (Vite + React + MapLibre).
cd web
npm ci
