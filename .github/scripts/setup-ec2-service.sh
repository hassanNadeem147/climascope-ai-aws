#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 3 ]]; then
  echo "Usage: sudo bash setup-ec2-service.sh DEPLOY_USER DEPLOY_PATH EXISTING_ENV_FILE" >&2
  exit 2
fi
if [[ "$EUID" -ne 0 ]]; then
  echo "Run this one-time setup script with sudo." >&2
  exit 1
fi

deploy_user="$1"
deploy_path="$2"
source_env="$3"

if [[ ! "$deploy_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "DEPLOY_USER contains unsupported characters." >&2
  exit 2
fi
if [[ "$deploy_user" != "clima-deploy" || "$deploy_path" != "/home/$deploy_user/apps/clima" ]]; then
  echo "Use deploy user clima-deploy and path /home/clima-deploy/apps/clima." >&2
  exit 2
fi
if [[ "$source_env" != "/home/ubuntu/apps/clima/.env" ]]; then
  echo "The existing environment file must be /home/ubuntu/apps/clima/.env." >&2
  exit 2
fi
if [[ ! -f "$source_env" || -L "$source_env" ]]; then
  echo "The existing environment file is missing or is not a regular file." >&2
  exit 1
fi
if [[ "$(stat -c '%U' "$source_env")" != "ubuntu" || "$(stat -c '%a' "$source_env")" != "600" ]]; then
  echo "The existing environment file must be owned by ubuntu with mode 600." >&2
  exit 1
fi
if ! command -v visudo >/dev/null || ! command -v systemctl >/dev/null || ! command -v openssl >/dev/null; then
  echo "visudo, systemctl, and openssl are required on EC2." >&2
  exit 1
fi
if [[ -e /etc/systemd/system/climascope-ai.service || -e /etc/sudoers.d/climascope-ai-deploy ]]; then
  echo "A ClimaScope service or sudoers file already exists; refusing to overwrite it." >&2
  exit 1
fi
if [[ -e "$deploy_path/.env" ]]; then
  echo "The destination environment file already exists; refusing to overwrite it." >&2
  exit 1
fi
if id "$deploy_user" >/dev/null 2>&1; then
  echo "The deployment account already exists; refusing to reuse an account with unknown privileges." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "$tmp_dir"' EXIT

useradd --create-home --user-group --home-dir "/home/$deploy_user" --shell /bin/bash "$deploy_user"
generated_password="$(openssl rand -base64 48)"
printf '%s:%s\n' "$deploy_user" "$generated_password" | chpasswd
unset generated_password

install -d -o "$deploy_user" -g "$deploy_user" -m 0750 "$deploy_path" "$deploy_path/releases"
install -o "$deploy_user" -g "$deploy_user" -m 0600 "$source_env" "$deploy_path/.env"
install -d -o "$deploy_user" -g "$deploy_user" -m 0700 "/home/$deploy_user/.ssh"

sed \
  -e "s|__DEPLOY_USER__|$deploy_user|g" \
  -e "s|__DEPLOY_PATH__|$deploy_path/current|g" \
  .github/systemd/climascope-ai.service > "$tmp_dir/climascope-ai.service"
sed \
  -e "s|__DEPLOY_USER__|$deploy_user|g" \
  .github/sudoers/climascope-deploy > "$tmp_dir/climascope-ai-deploy"

if grep -Eq '__DEPLOY_(USER|PATH)__' "$tmp_dir/climascope-ai.service" "$tmp_dir/climascope-ai-deploy"; then
  echo "Service templates contain unresolved placeholders." >&2
  exit 1
fi
visudo -cf "$tmp_dir/climascope-ai-deploy"

install -o root -g root -m 0644 \
  "$tmp_dir/climascope-ai.service" /etc/systemd/system/climascope-ai.service
install -o root -g root -m 0440 \
  "$tmp_dir/climascope-ai-deploy" /etc/sudoers.d/climascope-ai-deploy
systemctl daemon-reload
systemctl enable climascope-ai.service

printf '%s\n' \
  "One-time setup completed." \
  "Deployment user: $deploy_user (not in sudo/admin groups)" \
  "Deployment path: $deploy_path" \
  "Environment file copied with owner $deploy_user and mode 600." \
  "Add a dedicated SSH public key to /home/$deploy_user/.ssh/authorized_keys before deployment." \
  "GitHub Actions can sudo only: /usr/bin/systemctl restart climascope-ai.service" \
  "Update GitHub DEPLOY_USER and DEPLOY_PATH secrets before enabling deployment."
