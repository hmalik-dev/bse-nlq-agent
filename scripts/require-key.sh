# Sourced by dev.sh and smoke.sh from the repository root: stop before anything
# installs or starts when no API key is in the shell or in .env (the app reads
# .env itself). The app never answers without the real model.
key_var=ANTHROPIC_API_KEY
key_in_shell=${!key_var:-}
if [[ -z "${key_in_shell//[[:space:]]/}" ]] && ! grep -qE "^$key_var=.*[^[:space:]]" .env 2>/dev/null; then
  echo "ANTHROPIC_API_KEY is not set. Create .env with the ANTHROPIC_API_KEY= line you were sent, then run npm run dev again." >&2
  exit 1
fi
