#!/bin/zsh
set -euo pipefail

BASE_URL=""
USER_ID=""
CONFIG_DIR="$HOME/.openclaw/services/memos-client"
ENV_FILE="$CONFIG_DIR/.env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --user-id)
      USER_ID="$2"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Usage:
  onboard_memos_client.sh --base-url http://<SERVER_IP>:8765 [--user-id LinZhiYan]

What it does:
  1. Writes a local client env file for MemOS
  2. Runs a real add/search smoke test against the remote MemOS server

Notes:
  - This script does not modify openclaw.json yet.
  - It prepares a clean reusable client-side connection point first.
EOF
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$BASE_URL" ]]; then
  echo "Missing --base-url" >&2
  exit 1
fi

mkdir -p "$CONFIG_DIR"
if [[ -z "$USER_ID" ]]; then
  USER_ID="$(hostname -s)"
fi

cat > "$ENV_FILE" <<EOF
MEMOS_BASE_URL=$BASE_URL
MEMOS_USER_ID=$USER_ID
EOF
chmod 600 "$ENV_FILE"

echo "Wrote $ENV_FILE"
echo "Running smoke test against $BASE_URL ..."
python3 /Users/scott/.openclaw/workspace/scripts/memos_client_smoke_test.py --base-url "$BASE_URL" --user-id "$USER_ID"

echo "Done."
echo "Saved client defaults:"
echo "  MEMOS_BASE_URL=$BASE_URL"
echo "  MEMOS_USER_ID=$USER_ID"
