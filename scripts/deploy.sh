#!/usr/bin/env bash
# Deploy the hosted demo to Fly.io, or redeploy it: one command, safe to repeat.
# Creates the app and its volume only when they are missing, sets the API key
# as a Fly secret from this shell's environment (piped, so it never sits in a
# process's command line), then runs `fly deploy`.
#
# Needs: flyctl, a Fly login (`fly auth login`, or FLY_API_TOKEN), and
# ANTHROPIC_API_KEY exported in this shell. Use a dedicated key with a spend
# cap set in the Anthropic console, not the one in .env. The app name and
# region come from fly.toml; FLY_ORG picks the Fly organisation (default:
# personal). To rebuild the database once, run `fly deploy -e NLQ_RESEED=1`
# and then this script again, which clears the flag (a machine env persists).
set -euo pipefail
cd "$(dirname "$0")/.."

fail() {
  echo "deploy: $*" >&2
  exit 1
}

[[ -n "${ANTHROPIC_API_KEY:-}" ]] \
  || fail "ANTHROPIC_API_KEY is not set. Export a dedicated, spend-capped key in this shell."
if command -v flyctl >/dev/null 2>&1; then
  fly=flyctl
elif command -v fly >/dev/null 2>&1; then
  fly=fly
else
  fail "flyctl is not installed: https://fly.io/docs/flyctl/install/"
fi
"$fly" auth whoami >/dev/null 2>&1 \
  || fail "not logged in to Fly. Run '$fly auth login' or export FLY_API_TOKEN."

app=$(sed -n 's/^app = "\(.*\)"$/\1/p' fly.toml)
region=$(sed -n 's/^primary_region = "\(.*\)"$/\1/p' fly.toml)
[[ -n "$app" && -n "$region" ]] || fail "fly.toml must name an app and a primary_region."

if "$fly" status --app "$app" >/dev/null 2>&1; then
  echo "==> app $app exists"
else
  echo "==> creating app $app"
  "$fly" apps create "$app" --org "${FLY_ORG:-personal}"
fi

volumes=$("$fly" volumes list --app "$app" --json)
if grep -q '"name": *"data"' <<<"$volumes"; then
  echo "==> volume data exists"
else
  echo "==> creating the 1 GB volume data in $region"
  "$fly" volumes create data --app "$app" --region "$region" --size 1 --yes
fi

echo "==> setting the API key as a Fly secret (from the environment, over stdin)"
printf 'ANTHROPIC_API_KEY=%s\n' "$ANTHROPIC_API_KEY" | "$fly" secrets import --app "$app" --stage

echo "==> deploying"
"$fly" deploy --app "$app" --ha=false
echo "Deployed. Health: https://$app.fly.dev/api/health"
