# Sourced by dev.sh and smoke.sh from the repository root: stop before anything
# installs or starts when the app would have no API key. The app reads .env
# itself without overriding the shell, so a variable set in the shell wins even
# when it is blank. The app never answers without the real model.
key_var=ANTHROPIC_API_KEY
if [[ -n "${!key_var+set}" ]]; then
  key_in_shell=${!key_var}
  [[ -n "${key_in_shell//[[:space:]]/}" ]]
else
  grep -qE "^[[:space:]]*(export[[:space:]]+)?$key_var=.*[^[:space:]\"']" .env 2>/dev/null
fi || {
  echo "ANTHROPIC_API_KEY is not set. Create .env with the ANTHROPIC_API_KEY= line you were sent, then run npm run dev again." >&2
  exit 1
}
