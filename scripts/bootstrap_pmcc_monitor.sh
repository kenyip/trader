#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONITOR_SCRIPT="${HOME}/.hermes/scripts/pmcc_monitor.sh"

echo "PMCC monitor bootstrap"
echo "Repo: ${REPO_DIR}"

cd "${REPO_DIR}"

if ! command -v just >/dev/null 2>&1; then
  echo "Missing 'just'. Install it first (Arch: sudo pacman -S just; Ubuntu: sudo apt install just or use cargo)." >&2
  exit 1
fi

just setup

if [ ! -f pmcc_positions.yaml ]; then
  cp pmcc_positions.example.yaml pmcc_positions.yaml
  echo "Created pmcc_positions.yaml from example. Edit it with your real fills before relying on alerts."
else
  echo "Found existing pmcc_positions.yaml. Leaving it unchanged."
fi

mkdir -p "$(dirname "${MONITOR_SCRIPT}")"
cat > "${MONITOR_SCRIPT}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_DIR}"
.venv/bin/python pmcc_manage.py --monitor --quiet-ok
EOF
chmod +x "${MONITOR_SCRIPT}"

echo "Wrote ${MONITOR_SCRIPT}"
echo
echo "Smoke checks:"
.venv/bin/python -m py_compile pmcc_manage.py pmcc/income.py pmcc/positions.py
.venv/bin/python pmcc_manage.py --monitor || true

echo
echo "Next on the 24/7 Hermes box:"
echo "  1. Configure Hermes model/provider: hermes setup or hermes model"
echo "  2. Configure Telegram gateway: hermes gateway setup telegram"
echo "  3. Install/start gateway: hermes gateway install && hermes gateway start"
echo "  4. Create cron monitor: hermes cron create '*/30 7-13 * * 1-5' --script pmcc_monitor.sh --no-agent"
echo
