#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo "Expected deploy user, deploy path, and release name." >&2
  exit 2
fi

deploy_user="$1"
deploy_path="$2"
release_name="$3"

if [[ ! "$deploy_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "DEPLOY_USER contains unsupported characters." >&2
  exit 2
fi
if [[ ! "$deploy_path" =~ ^/home/[A-Za-z0-9._/-]+$ || "$deploy_path" == *"/../"* || "$deploy_path" == */.. || "$deploy_path" != "/home/$deploy_user/"* ]]; then
  echo "DEPLOY_PATH must be a safe directory under the deploy user's home." >&2
  exit 2
fi
if [[ ! "$release_name" =~ ^[0-9a-f]{40}-[0-9]+-[0-9]+$ ]]; then
  echo "Release name is invalid." >&2
  exit 2
fi
release_path="$deploy_path/releases/$release_name"
current_path="$deploy_path/current"

if [[ ! -d "$deploy_path" || ! -f "$deploy_path/.env" ]]; then
  echo "Deployment directory or .env is missing; existing .env was not changed." >&2
  exit 1
fi
if [[ ! -d "$release_path" || ! -f "$release_path/requirements.txt" ]]; then
  echo "Uploaded release files are missing." >&2
  exit 1
fi
if [[ ! -f /etc/systemd/system/climascope-ai.service ]]; then
  echo "climascope-ai.service is not installed. Run the one-time EC2 setup instructions first." >&2
  exit 1
fi
if [[ ! -x /usr/bin/systemctl ]]; then
  echo "systemctl was not found at /usr/bin/systemctl." >&2
  exit 1
fi
if ! command -v python3 >/dev/null; then
  echo "Python 3 is not installed on EC2." >&2
  exit 1
fi
python3 -c 'import sys; sys.version_info >= (3, 12) or sys.exit("Python 3.12 or newer is required")'

previous_release="$(readlink -f "$current_path" 2>/dev/null || true)"
if [[ -n "$previous_release" && "$previous_release" != "$deploy_path"/releases/* ]]; then
  echo "Current release symlink points outside the releases directory; refusing deployment." >&2
  exit 1
fi

ln -s "$deploy_path/.env" "$release_path/.env"
mkdir -p "$release_path/logs"
python3 -m venv "$release_path/.venv"
"$release_path/.venv/bin/python" -m pip install --no-cache-dir -r "$release_path/requirements.txt"

next_link="$deploy_path/.current-$release_name"
ln -s "$release_path" "$next_link"
mv -Tf "$next_link" "$current_path"

if sudo -n /usr/bin/systemctl restart climascope-ai.service; then
  for attempt in {1..60}; do
    if curl --fail --silent --max-time 3 http://127.0.0.1:5555/health >/dev/null; then
      echo "Deployment is healthy."
      for old_release in "$deploy_path"/releases/*; do
        [[ -d "$old_release" ]] || continue
        [[ "$old_release" == "$release_path" || "$old_release" == "$previous_release" ]] && continue
        old_name="${old_release##*/}"
        if [[ "$old_name" =~ ^[0-9a-f]{40}-[0-9]+-[0-9]+$ ]]; then
          rm -rf -- "$old_release"
        fi
      done
      exit 0
    fi
    sleep 5
  done
fi

echo "Deployment health check failed." >&2
if [[ -n "$previous_release" && -d "$previous_release" ]]; then
  rollback_link="$deploy_path/.rollback-$release_name"
  ln -s "$previous_release" "$rollback_link"
  mv -Tf "$rollback_link" "$current_path"
  sudo -n /usr/bin/systemctl restart climascope-ai.service || true
fi
exit 1
