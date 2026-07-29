#!/usr/bin/env bash
#
# Sync the Summer Grandeur lot photographs between this repo and Cloudflare R2.
#
# Only the images move. lots.csv, meta.json, lot-urls.txt and the HTML captures
# stay in git — they are ~150 MB and they are the part worth diffing.
#
#   scripts/r2.sh check     verify credentials and reach the bucket
#   scripts/r2.sh status    dry run: what push/pull would change
#   scripts/r2.sh push      upload local images to R2 (mirror; deletes on R2)
#   scripts/r2.sh pull      download images from R2 (never deletes locally)
#   scripts/r2.sh browser   print the settings for an S3 browser app
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.r2"
LOCAL_DIR="$REPO_ROOT/data"
REMOTE_PREFIX="data"

# Images only. Patterns are relative to the sync root (data/).
FILTERS=(--include "/*/lots/*/images/**")

# rclone tuning: 5,217 small-to-medium JPEGs, so parallelism beats chunk size.
RCLONE_OPTS=(--transfers 16 --checkers 32 --retries 5 --stats 5s)

die() { printf '\033[0;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[0;36m==>\033[0m %s\n' "$*"; }

require_rclone() {
  command -v rclone >/dev/null 2>&1 && return 0
  cat >&2 <<'EOF'
error: rclone is not installed.

  macOS          brew install rclone
  Debian/Ubuntu  sudo apt install rclone      (needs >= 1.59; else use the script below)
  any Linux      curl https://rclone.org/install.sh | sudo bash
  Windows        winget install Rclone.Rclone

rclone is used instead of the AWS CLI because it diffs 5,217 files before
transferring, resumes cleanly, and does not trip R2's CRC32 checksum
incompatibility.
EOF
  exit 1
}

load_env() {
  [ -f "$ENV_FILE" ] || die ".env.r2 not found. Run: cp .env.r2.example .env.r2 && \$EDITOR .env.r2"
  set -a; . "$ENV_FILE"; set +a

  local missing=()
  for v in R2_ACCOUNT_ID R2_BUCKET R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY; do
    [ -n "${!v:-}" ] || missing+=("$v")
  done
  [ ${#missing[@]} -eq 0 ] || die "unset in .env.r2: ${missing[*]}"

  # Define the remote through the environment so no secret is ever written to
  # an rclone config file on disk.
  export RCLONE_CONFIG_R2_TYPE=s3
  export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
  export RCLONE_CONFIG_R2_REGION=auto
  export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
  export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
  # R2 has no ACLs; sending one is rejected on some paths.
  export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

  REMOTE="r2:${R2_BUCKET}/${REMOTE_PREFIX}"
}

count_local() { find "$LOCAL_DIR" -path '*/lots/*/images/*' -type f 2>/dev/null | wc -l | tr -d ' '; }

cmd_check() {
  load_env; require_rclone
  info "endpoint  https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  info "bucket    ${R2_BUCKET}"
  rclone lsd "r2:${R2_BUCKET}" >/dev/null 2>&1 \
    || die "cannot reach the bucket. Check R2_ACCOUNT_ID, the bucket name, and that the token has Object Read & Write on this bucket."
  info "connected."
  info "local images   $(count_local)"
  info "remote objects $(rclone size "$REMOTE" --json 2>/dev/null | jq -r '"\(.count) files, \(.bytes/1e9|floor) GB"' 2>/dev/null || echo 'empty or unreadable')"
}

cmd_status() {
  load_env; require_rclone
  info "push would change (dry run):"
  rclone sync "$LOCAL_DIR" "$REMOTE" "${FILTERS[@]}" --dry-run --stats 0
  info "pull would change (dry run):"
  rclone copy "$REMOTE" "$LOCAL_DIR" "${FILTERS[@]}" --dry-run --stats 0
}

cmd_push() {
  load_env; require_rclone
  local n; n="$(count_local)"
  [ "$n" -gt 0 ] || die "no images found under data/*/lots/*/images/ — refusing to mirror an empty tree onto R2."
  info "mirroring $n local images to $REMOTE"
  info "this deletes anything on R2 under $REMOTE_PREFIX/ that is not present locally."
  rclone sync "$LOCAL_DIR" "$REMOTE" "${FILTERS[@]}" "${RCLONE_OPTS[@]}" --progress
  info "done. Verify with: scripts/r2.sh check"
}

cmd_pull() {
  load_env; require_rclone
  info "downloading images from $REMOTE into data/"
  # copy, not sync: never delete local files.
  rclone copy "$REMOTE" "$LOCAL_DIR" "${FILTERS[@]}" "${RCLONE_OPTS[@]}" --progress
  info "done. local images: $(count_local)"
}

cmd_browser() {
  load_env
  cat <<EOF

Settings for an S3 browser (Cyberduck, S3 Browser, WinSCP, Transmit, Mountain Duck):

  Provider / type      S3 (Amazon S3 compatible) — not "Cloudflare", most apps
                       do not have an R2 preset; the generic S3 profile is right
  Server / endpoint    ${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
  URL form             https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
  Port                 443
  Region               auto
  Access Key ID        (R2_ACCESS_KEY_ID from .env.r2)
  Secret Access Key    (R2_SECRET_ACCESS_KEY from .env.r2)
  Bucket / path        ${R2_BUCKET}
  Addressing style     path-style
  Signature version    v4

If the app shows no buckets after connecting, the token is scoped to one
bucket and cannot run ListBuckets. Point it straight at the path
"${R2_BUCKET}" (Cyberduck: put it in the Path field) instead of browsing.

EOF
}

case "${1:-}" in
  check)   cmd_check ;;
  status)  cmd_status ;;
  push)    cmd_push ;;
  pull)    cmd_pull ;;
  browser) cmd_browser ;;
  *) sed -n '3,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 1 ;;
esac
