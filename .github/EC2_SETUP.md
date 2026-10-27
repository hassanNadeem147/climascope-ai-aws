# One-time EC2 setup

The deployment workflow does not clone the repository on EC2. GitHub Actions
uploads each release over SSH. Before merging a change to `main`, install the
service once on EC2 and update the deployment secrets as described below.

## 1. Get the setup files onto EC2 without deploying

From the EC2 terminal, clone a branch that contains these `.github` files. The
read-only GitHub deploy key already configured on EC2 can be used for this:

```bash
git clone --branch YOUR_BRANCH --single-branch \
  git@github.com:hassanNadeem147/ClimaScope-AI.git \
  ~/climascope-bootstrap
cd ~/climascope-bootstrap
```

Replace `YOUR_BRANCH` with the branch name pushed from your computer. Do not
clone or check out `main` to trigger deployment before completing this setup.

## 2. Install the service and restricted deployment account once

Run this on EC2 as the existing `ubuntu` administrator:

```bash
sudo bash .github/scripts/setup-ec2-service.sh \
  clima-deploy \
  /home/clima-deploy/apps/clima \
  /home/ubuntu/apps/clima/.env
```

The script creates an unprivileged `clima-deploy` account and copies `.env`
without printing its contents. It installs the root-owned systemd service and
a sudoers rule that permits that deployment account to run only:

```text
/usr/bin/systemctl restart climascope-ai.service
```

It refuses to overwrite an existing service or sudoers file. It enables the
service at boot but does not start it until the first release is deployed.
Keep the existing `ubuntu` account for administration; do not use it as the
GitHub Actions deployment account because it has administrative privileges.

The setup script requires the source `.env` to be a regular file owned by
`ubuntu` with mode `600`. The destination copy is owned by `clima-deploy` with
mode `600`. The two files are independent; changing one does not update the
other. After setup, maintain the runtime configuration at
`/home/clima-deploy/apps/clima/.env`.

## 3. Create a dedicated SSH key for GitHub Actions

Do not reuse the EC2 administrator private key (`clima-key.pem`) as the GitHub
Actions deployment key. Create a separate key on your computer. In Windows
PowerShell:

```powershell
ssh-keygen -t ed25519 -C github-actions-climascope -f "$HOME\.ssh\climascope-actions"
```

When prompted for a passphrase, press Enter twice to leave it empty; GitHub
Actions cannot answer an interactive passphrase prompt. Keep
`climascope-actions` private and never paste it into chat or commit it.

Print only the public key:

```powershell
Get-Content "$HOME\.ssh\climascope-actions.pub"
```

Copy that one `ssh-ed25519 ...` public-key line. On EC2, install it for the
deployment account, replacing `PASTE_PUBLIC_KEY_LINE_HERE` locally with the
public-key line:

```bash
printf '%s\n' 'PASTE_PUBLIC_KEY_LINE_HERE' | sudo tee /home/clima-deploy/.ssh/authorized_keys >/dev/null
sudo chown clima-deploy:clima-deploy /home/clima-deploy/.ssh/authorized_keys
sudo chmod 600 /home/clima-deploy/.ssh/authorized_keys
```

The public key is not secret. Do not paste the private key into the EC2
terminal.

## 4. Update GitHub Actions secrets

Under **Repository → Settings → Secrets and variables → Actions**, update:

| Secret | Required value |
| --- | --- |
| `DEPLOY_USER` | `clima-deploy` |
| `DEPLOY_PATH` | `/home/clima-deploy/apps/clima` |
| `DEPLOY_SSH_KEY` | Full contents of the private file `climascope-actions` (not the `.pub` file) |

Keep the existing `DEPLOY_HOST` and `DEPLOY_KNOWN_HOSTS` secrets, after
verifying that the host-key secret is for EC2. Never put `.env` values into
GitHub Actions secrets for this workflow and never commit or print `.env`.

`DEPLOY_KNOWN_HOSTS` must contain the EC2 server host key for the host in
`DEPLOY_HOST`, not GitHub's host key. On EC2, the public host key can be printed
with:

```bash
printf '13.63.33.88 '; sudo cat /etc/ssh/ssh_host_ed25519_key.pub
```

Verify the host key fingerprint through your trusted EC2 session, then store
that complete output as the `DEPLOY_KNOWN_HOSTS` secret. If `DEPLOY_HOST` is
not `13.63.33.88`, use its actual value in place of that IP.

## 5. Deploy through a pull request

Push the `.github` changes to a non-`main` branch and open a pull request. The
pull request runs validation only. After one-time EC2 setup is complete, merge
the pull request to `main`; that push triggers deployment. You can also use
**Actions → CI/CD → Run workflow** on `main`.

The deployment creates a versioned release, installs its dependencies, switches
the `current` symlink, restarts the fixed systemd service, and checks
`http://127.0.0.1:5555/health`. If health verification fails after a prior
release exists, it restores the prior release and attempts to restart it.

The EC2 security group must allow SSH from the GitHub Actions runner. Do not
expose SSH to `0.0.0.0/0`; use a controlled runner/network approach and keep
strict SSH host-key verification enabled.
