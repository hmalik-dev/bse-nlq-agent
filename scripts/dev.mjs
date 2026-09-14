// One command from a clone to the app in a browser, on macOS, Linux and Windows:
// install what is missing, seed on first run only, start the API on :8000, then
// the Vite dev server on :4000, which opens the browser and proxies /api to the
// API. Ctrl+C stops both. Stops before anything runs when there is no API key.
// Run as `npm run dev`; `node scripts/dev.mjs --check-key` runs only the key check.
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { existsSync, readFileSync, realpathSync } from "node:fs";
import { connect } from "node:net";
import { delimiter, join } from "node:path";
import { setTimeout as pause } from "node:timers/promises";
import { fileURLToPath, pathToFileURL } from "node:url";

const API_HOST = "127.0.0.1";
const API_PORT = 8000;
const UI_PORT = 4000;
const READY_TIMEOUT_S = 30;
const NODE_MAJOR_REQUIRED = 24; // the major CI uses (.github/workflows/ci.yml)
const NODE_DOWNLOAD = "https://nodejs.org/en/download";
const KEY_VAR = "ANTHROPIC_API_KEY";
const NO_KEY_LINE = `${KEY_VAR} is not set. Create .env with the ${KEY_VAR}= line you were sent, then run npm run dev again.`;
const IS_WINDOWS = process.platform === "win32";

/** The uv installer one-liner for this platform's own shell. */
export function uvInstallHint(platform) {
  if (platform === "win32") {
    return 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"';
  }
  return "curl -LsSf https://astral.sh/uv/install.sh | sh";
}

const REQUIRED_TOOLS = [
  ["uv", uvInstallHint(process.platform)],
  ["npm", `it ships with Node: ${NODE_DOWNLOAD}`],
];

class LauncherError extends Error {}

function say(line) {
  process.stdout.write(`==> ${line}\n`);
}

/** The sentence refusing a Node older than the one CI uses, or null when it is new enough. */
export function nodeVersionProblem(version) {
  const major = Number(/^v(\d+)\./.exec(version)?.[1]);
  if (major >= NODE_MAJOR_REQUIRED) return null;
  return `Node ${NODE_MAJOR_REQUIRED} or newer is required; found ${version}: ${NODE_DOWNLOAD}`;
}

function isOnPath(tool) {
  const extensions = IS_WINDOWS ? (process.env.PATHEXT ?? ".EXE;.CMD").split(";") : [""];
  const dirs = (process.env.PATH ?? "").split(delimiter).filter(Boolean);
  return dirs.some((dir) => extensions.some((ext) => existsSync(join(dir, tool + ext))));
}

function requireTools() {
  for (const [tool, hint] of REQUIRED_TOOLS) {
    if (!isOnPath(tool)) throw new LauncherError(`${tool} is not installed: ${hint}`);
  }
  const problem = nodeVersionProblem(process.version);
  if (problem) throw new LauncherError(problem);
}

/**
 * The app reads .env itself without overriding the shell, so a variable set in the
 * shell wins even when it is blank. The app never answers without the real model.
 */
export function hasKey(env, envFileText) {
  if (Object.hasOwn(env, KEY_VAR)) return env[KEY_VAR].trim() !== "";
  const line = new RegExp(`^[ \\t]*(export[ \\t]+)?${KEY_VAR}=.*[^\\s"']`, "m");
  return line.test(envFileText ?? "");
}

function requireKey() {
  const envFileText = existsSync(".env") ? readFileSync(".env", "utf8") : null;
  if (!hasKey(process.env, envFileText)) throw new LauncherError(NO_KEY_LINE);
}

/**
 * Runs `command` with `spawner` (spawn or spawnSync). npm is a .cmd shim on Windows,
 * which only a shell can start, and a shell takes one command line, not an argument list.
 */
function runCommand(spawner, command, args, options = {}) {
  const viaShell = IS_WINDOWS && command === "npm";
  const settings = { stdio: "inherit", shell: viaShell, ...options };
  if (viaShell) return spawner([command, ...args].join(" "), settings);
  return spawner(command, args, settings);
}

function runStep(command, args) {
  const result = runCommand(spawnSync, command, args);
  if (result.status !== 0) throw new LauncherError(`FAIL: ${command} ${args[0]} did not succeed`);
}

function databasePath() {
  const code = "from nlq.config import DATABASE_PATH; print(DATABASE_PATH)";
  const options = { stdio: ["ignore", "pipe", "inherit"], encoding: "utf8" };
  const result = runCommand(spawnSync, "uv", ["run", "python", "-c", code], options);
  if (result.status !== 0) throw new LauncherError("FAIL: could not resolve the database path");
  return result.stdout.trim();
}

function installAndSeed() {
  say("uv sync");
  runStep("uv", ["sync"]);
  if (!existsSync("node_modules")) {
    say("npm ci");
    runStep("npm", ["ci"]);
  }
  const database = databasePath();
  if (existsSync(database)) {
    say(`using the existing database at ${database}`);
    return;
  }
  say(`seeding ${database} at scale 0.2 (first run only)`);
  runStep("uv", ["run", "python", "-m", "nlq.db.seed", "--scale", "0.2"]);
}

function isListening(port) {
  return new Promise((resolve) => {
    const socket = connect({ host: API_HOST, port });
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => resolve(false));
  });
}

/** Stops a child and everything it started: a process group on POSIX, a tree on Windows. */
export function stopTree(child, { platform = process.platform, runSync = spawnSync } = {}) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  if (platform === "win32") {
    runSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  try {
    process.kill(-child.pid, "SIGINT");
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }
}

/** Stops the API, waits until it has exited, then ends the launcher with `code`. */
async function stopApiAndExit(api, code) {
  if (api && api.exitCode === null && api.signalCode === null) {
    const exited = once(api, "exit");
    stopTree(api);
    await exited;
  }
  process.exit(code);
}

async function isHealthy() {
  try {
    const response = await fetch(`http://${API_HOST}:${API_PORT}/api/health`);
    return response.ok && (await response.json()).database === true;
  } catch {
    return false; // not listening yet, or not answering JSON yet
  }
}

async function waitForApi(api) {
  for (let second = 0; second < READY_TIMEOUT_S; second += 1) {
    if (api.exitCode !== null || api.signalCode !== null) {
      throw new LauncherError(
        `FAIL: the API did not start. Is port ${API_PORT} already in use? (lsof -i :${API_PORT})`,
      );
    }
    if (await isHealthy()) return;
    await pause(1000);
  }
  throw new LauncherError(
    `FAIL: /api/health on port ${API_PORT} did not report database: true within ${READY_TIMEOUT_S}s`,
  );
}

function startApi() {
  say(`starting the API on port ${API_PORT}`);
  const args = ["run", "uvicorn", "nlq.api:app", "--reload", "--host", API_HOST, "--port", String(API_PORT)];
  // Its own process group on POSIX, so stopTree reaches the reloader's worker too.
  return runCommand(spawn, "uv", args, { detached: !IS_WINDOWS });
}

function startUi() {
  say(`opening http://localhost:${UI_PORT} (Ctrl+C stops everything)`);
  const args = ["run", "-w", "web", "dev", "--", "--port", String(UI_PORT), "--strictPort", "--open"];
  return runCommand(spawn, "npm", args);
}

async function launch(processes) {
  requireKey();
  requireTools();
  installAndSeed();
  // A server already on the port would answer the health check in place of ours.
  if (await isListening(API_PORT)) {
    throw new LauncherError(`FAIL: port ${API_PORT} is already in use (lsof -i :${API_PORT}).`);
  }
  processes.api = startApi();
  await waitForApi(processes.api);
  processes.ui = startUi();
  processes.ui.once("exit", (code) => void stopApiAndExit(processes.api, code ?? 0));
}

async function main() {
  process.chdir(fileURLToPath(new URL("..", import.meta.url)));
  const processes = { api: null, ui: null };
  // Ctrl+C reaches the UI from the terminal; a kill or a closed terminal may reach only us.
  // The API runs in its own process group, so nothing but stopTree reaches it.
  const stopOnSignal = () => {
    processes.ui?.kill("SIGTERM");
    void stopApiAndExit(processes.api, 130);
  };
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(signal, stopOnSignal);
  try {
    if (process.argv.includes("--check-key")) requireKey();
    else await launch(processes);
  } catch (error) {
    if (!(error instanceof LauncherError)) throw error;
    process.stderr.write(`${error.message}\n`);
    await stopApiAndExit(processes.api, 1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  await main();
}
