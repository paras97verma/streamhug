#!/usr/bin/env zsh
# ──────────────────────────────────────────────────────────────────────────────
# StreamHug — Docker Runner & zrok Tunnel Retriever
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Animations & Helpers ──────────────────────────────────────────────────────
typewrite() {
    local text="$1"
    local delay="${2:-0.05}"
    echo -e "$text"
    sleep "$delay"
}

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
typewrite "${CYAN}${BOLD}  ╔═══════════════════════════════════════════════════╗${RESET}" 0.005
typewrite "${CYAN}${BOLD}  ║         ◈  StreamHug Docker & zrok Runner         ║${RESET}" 0.01
typewrite "${CYAN}${BOLD}  ╚═══════════════════════════════════════════════════╝${RESET}" 0.005
echo ""

# ── Check Docker ──────────────────────────────────────────────────────────────
typewrite "${BOLD}  🐳 Checking Docker status...${RESET}"
if ! docker info >/dev/null 2>&1; then
    echo "${RED}  ✗ Docker is not running. Please start Docker Desktop first.${RESET}"
    exit 1
fi
echo "${GREEN}  ✓ Docker is running${RESET}"
echo ""

# ── Check Env Variables ───────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
    echo "${RED}  ✗ Root .env file is missing! Please configure .env first.${RESET}"
    exit 1
fi

ZROK_ENABLE_TOKEN=$(grep -E "^ZROK_ENABLE_TOKEN=" ".env" 2>/dev/null | cut -d'=' -f2- | tr -d ' ' | tr -d '"' | tr -d "'")

if [[ -z "$ZROK_ENABLE_TOKEN" ]]; then
    echo "${RED}  ✗ ZROK_ENABLE_TOKEN is missing or empty in your .env file!${RESET}"
    echo "    To access StreamHug publicly over the internet via zrok, please:"
    echo "    1. Sign up for a free account at ${BOLD}https://zrok.io${RESET}"
    echo "    2. Get your enablement token from the zrok dashboard."
    echo "    3. Add ${BOLD}ZROK_ENABLE_TOKEN=\"your_token_here\"${RESET} to your ${BOLD}.env${RESET} file."
    echo "    4. Run ${BOLD}./run_docker.sh${RESET} again."
    echo ""
    echo "    Alternatively, you can access the application locally at: http://localhost:3000"
    exit 1
fi

# ── Build & Start Docker App ──────────────────────────────────────────────────
typewrite "${BOLD}  🚀 Building and launching self-contained Docker containers...${RESET}"
docker compose down --remove-orphans 2>/dev/null || true
docker rm -f streamhug-backend streamhug-frontend streamhug-zrok 2>/dev/null || true
docker compose up --build -d

# Wait for backend healthcheck (via Nginx proxy on port 3000)
typewrite "${BOLD}  ⏳ Waiting for app healthcheck to pass...${RESET}"
HTTP_STATUS=""
for i in {1..30}; do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v1/health || true)
    if [[ "$HTTP_STATUS" == "200" ]]; then
        break
    fi
    sleep 1
done

if [[ "$HTTP_STATUS" != "200" ]]; then
    echo "${RED}  ✗ Healthcheck failed. Containers might have failed to start.${RESET}"
    echo "     Run: ${BOLD}docker compose logs${RESET} to check errors."
    exit 1
fi
echo "${GREEN}  ✓ Healthcheck passed${RESET}"
echo ""

# ── Retrieve Tunnel URL ────────────────────────────────────────────
PUBLIC_URL=""
typewrite "${BOLD}  🌐 Retrieving zrok Tunnel URL...${RESET}"
for i in {1..30}; do
    PUBLIC_URL=$(docker logs streamhug-zrok 2>&1 | grep -o -E "https://[a-zA-Z0-9.-]+\.share\.zrok\.io" | head -n 1 || true)
    if [[ -n "$PUBLIC_URL" ]]; then
        break
    fi
    sleep 1
done

if [[ -z "$PUBLIC_URL" ]]; then
    echo "${RED}  ✗ Failed to retrieve zrok public tunnel URL.${RESET}"
    echo "    Check the container logs using: ${BOLD}docker logs streamhug-zrok${RESET}"
    docker compose down
    exit 1
fi

typewrite "${GREEN}  ✓ Active zrok Tunnel URL: ${CYAN}${PUBLIC_URL}${RESET}"
echo ""

# Remove URL shortener cache file if it exists
rm -f .short_url_cache

# ── Success Frame ─────────────────────────────────────────────────────────────
echo ""
typewrite "${GREEN}${BOLD}  🎉 StreamHug is fully online!${RESET}" 0.05
typewrite "${DIM}  ─────────────────────────────────────────────────${RESET}" 0.02
typewrite "     Local App:        ${GREEN}http://localhost:3000${RESET}" 0.02
typewrite "     Public Tunnel:    ${CYAN}${PUBLIC_URL}${RESET}" 0.03
typewrite "${DIM}  ─────────────────────────────────────────────────${RESET}" 0.02
echo ""
typewrite "  ${YELLOW}Press Ctrl+C to stop the Docker stack${RESET}"
echo ""

# ── Graceful Shutdown ──────────────────────────────────────────────────────────
cleanup() {
    echo ""
    typewrite "${YELLOW}Stopping Docker containers...${RESET}"
    docker compose down
    typewrite "${GREEN}✓ All services stopped gracefully.${RESET}"
    exit 0
}

trap cleanup INT TERM

# Keep script running to maintain logs and trap Ctrl+C
while true; do
    sleep 1
done
