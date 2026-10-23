#!/usr/bin/env python3
"""Real DOM/CSS regression using Chromium and an in-page API fixture only."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


WEB = Path(__file__).resolve().parents[1] / "configs/x2000/rootfs-overlay/usr/share/fre3nder/web-root/maintenance"
CHROMIUM = shutil.which("chromium")

FIXTURE = r'''
let csrfToken = "fixture-csrf";
let rejectRemoval = true;
let posts = 0;
let displayRunning = true;
let rejectDisplayStatus = false;
let displayStatusReads = 0;
const app = {name: "doom", version: "1.0", release_serial: 1, publisher: "trusted", storage: "sys"};
const state = {
  installed: [app], web: {active: null}, display: {active: null, apps: []},
  packages: [], verified_packages: [], execution: null,
  storage: {available_bytes: 1024, max_package_bytes: 1024}
};
window.confirm = () => true;
const requestJson = async (url, options = {}) => {
  if (options.method === "POST") {
    posts++;
    const operation = url.split("/apps/")[1];
    const payload = JSON.parse(options.body);
    if (rejectRemoval && operation === "remove") throw new Error("service uninstall failed");
    state.execution = {id: String(posts), operation: operation.replace("/", "-"), ...payload,
      name: payload.name || appsVerified?.package?.name, state: "running"};
    return {execution: {...state.execution}};
  }
  if (url.includes("/apps/detail?name=")) {
    displayStatusReads++;
    if (rejectDisplayStatus) throw new Error("display status unavailable");
    return {app: {...app, name: decodeURIComponent(url.split("name=")[1]), running: displayRunning}};
  }
  return {apps: JSON.parse(JSON.stringify(state))};
};
'''

SCENARIOS = r'''
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const el = (name) => document.getElementById("apps-" + name);
  const waitForPoll = () => new Promise((resolve) => setTimeout(resolve, 1400));
  document.getElementById("apps-view").hidden = false;
  await appsLoad();
  await appsRemove(app);
  assert(el("remove-error-doom").offsetHeight > 0, "removal failure must be visible beside the app");
  assert(el("remove-error-doom").textContent.includes("doom"), "failure must name doom");
  assert(el("operation").dataset.state === "error", "request rejection must appear in the popup");
  assert(el("operation-result").textContent.includes("service uninstall failed"), "request failure details must be available");
  const red = getComputedStyle(el("remove-error-doom")).borderTopColor.match(/\d+/g).map(Number);
  assert(red[0] > red[1], "error box must be red");

  rejectRemoval = false;
  await appsRemove(app);
  assert(el("remove-error-doom").hidden, "new action must clear old error");
  assert(el("message").textContent === "Removing doom…", "running operation must name doom");
  assert(el("installed-success").hidden, "acceptance must not imply success");
  assert(el("installed").textContent.includes("doom"), "running operation must retain app");
  state.execution = {...state.execution, state: "succeeded", result: {name: "doom"}};
  await waitForPoll();
  assert(el("installed-success").hidden, "unchanged installed state must not report success");
  assert(el("remove-error-doom").textContent.includes("still installed"), "mismatch must explain the failure");
  assert(!el("execution").textContent.includes("succeeded"), "status must not claim unconfirmed success");

  await appsRemove(app);
  state.installed = [];
  state.execution = {...state.execution, state: "succeeded", result: {name: "doom"}};
  await waitForPoll();
  assert(!el("installed").textContent.includes("doom"), "confirmed removal must refresh the list automatically");
  assert(el("installed-success").offsetHeight > 0, "success box must be visible");
  assert(el("installed-success").textContent === 'App "doom" was removed successfully.', "success must name doom");
  assert(el("installed-success").closest("section").querySelector("h2").textContent === "Installed Apps", "success must be local");
  assert(el("installed-success").getAttribute("role") === "status", "success must be accessible");
  const green = getComputedStyle(el("installed-success")).borderTopColor.match(/\d+/g).map(Number);
  assert(green[1] > green[0], "success box must be green");
  assert(!document.querySelector("#apps-view .error:not([hidden])"), "success must not coexist with stale errors");
  assert(posts === 3, "polling must never repeat mutations");

  // Selecting a new invalid upload also dismisses the previous success receipt.
  el("upload-form").dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
  await Promise.resolve();
  await appsLoad();
  assert(el("installed-success").hidden, "new action must dismiss previous success");
  assert(el("upload-error").offsetHeight > 0, "new failure must be shown beside upload");
  document.getElementById("browser-result").textContent = "PASS";
})().catch((error) => { document.getElementById("browser-result").textContent = "FAIL: " + error.stack; });
'''

MODAL_SCENARIOS = r'''
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const el = (name) => document.getElementById("apps-" + name);
  const mirrored = () => {
    assert(el("operation-execution").textContent === el("execution").textContent, "modal and page status must match");
    assert(el("operation-result").textContent === el("result").textContent, "modal and page receipts must match");
  };
  document.getElementById("apps-view").hidden = false;
  document.body.style.minHeight = "2500px";
  rejectRemoval = false;
  for (const [operation, name, verb] of [["install", "doom", "Installing"], ["update", "fluidd", "Updating"], ["remove", "doom", "Removing"]]) {
    state.installed = operation === "install" ? [] : [{...app, name}];
    state.execution = null;
    const item = {...app, name, version: "2.0", release_serial: 2};
    const id = "a".repeat(32);
    state.packages = [{id, size: 12}]; state.verified_packages = [id];
    appsVerified = {id, package: item};
    await appsLoad();
    window.scrollTo(0, 2000);
    await appsAction(operation, operation === "remove" ? {name} : operation === "install" ? {package_id: id} : {package_id: id, name});
    const dialog = el("operation");
    assert(dialog.matches(":modal"), "operation must open a native modal");
    assert(el("operation-title").textContent === `${verb} ${name}…`, "popup must name action and app");
    assert(el("operation-spinner").offsetHeight > 0, "spinner must be visible");
    assert(!el("operation-details").open, "details must start collapsed");
    assert(el("operation-close").hidden, "running operation cannot be dismissed");
    const cancel = new Event("cancel", {cancelable: true});
    assert(!dialog.dispatchEvent(cancel), "Escape must not dismiss a running operation");
    const background = document.querySelector('a[href="#overview"]');
    background.focus();
    assert(document.activeElement !== background, "background must not accept keyboard focus");
    const calls = posts;
    await appsAction("remove", {name: "otherapp"});
    el("upload-form").dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
    assert(posts === calls, "concurrent actions must not reach the API");

    const summary = el("operation-details").querySelector("summary");
    summary.click(); assert(el("operation-details").open, "details must expand");
    summary.click(); assert(!el("operation-details").open, "details must collapse");
    summary.click();
    // Model a large live receipt; rendering must neither resize beyond the screen nor reset expansion.
    state.execution.log = "long receipt line\n".repeat(400);
    await appsLoad(); mirrored();
    assert(el("operation-details").open, "polling must preserve expanded details");
    const rect = dialog.getBoundingClientRect();
    assert(rect.top >= 0 && rect.bottom <= innerHeight, "modal must stay within viewport");
    const details = el("operation-result");
    assert(details.scrollHeight > details.clientHeight, "long details must scroll");
    assert(getComputedStyle(details).overflowY === "auto", "detail scrolling must be enabled");
    assert(posts === calls, "toggling details must not start operations");

    if (operation === "update") {
      state.execution = {...state.execution, state: "failed", error: {message: "fixture service failed"}};
    } else {
      state.installed = operation === "remove" ? [] : [item];
      state.execution = {...state.execution, state: "succeeded", result: operation === "remove" ? {name} : {package: item}};
    }
    await appsLoad(); mirrored();
    const failed = operation === "update";
    assert(dialog.dataset.state === (failed ? "error" : "success"), "modal must show final outcome");
    assert(el("operation-status").classList.contains(failed ? "error" : "success"), "outcome must use existing colors");
    const color = getComputedStyle(el("operation-status")).borderTopColor.match(/\d+/g).map(Number);
    assert(failed ? color[0] > color[1] : color[1] > color[0], "failure must be red and success green");
    assert(el("operation-title").textContent.includes(name), "final outcome must name app");
    assert(el("operation-details").open, "final details must remain expanded");
    assert(el("operation-spinner").hidden && !el("operation-close").hidden, "completed operation must be dismissible");
    assert(details.textContent.includes(failed ? "fixture service failed" : name), "final receipt must be displayed");
    if (operation === "remove") assert(!el("installed").textContent.includes(name), "successful removal must refresh list");
    el("operation-close").click();
    assert(!dialog.open, "Close must dismiss the completed modal");
    await appsLoad(); assert(!dialog.open, "consumed receipt must not reopen modal");
  }
  document.getElementById("browser-result").textContent = "PASS";
})().catch((error) => { document.getElementById("browser-result").textContent = "FAIL: " + error.stack; });
'''

DISPLAY_SCENARIO = r'''
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const el = (name) => document.getElementById("apps-" + name);
  document.getElementById("apps-view").hidden = false;
  state.installed = [{...app, storage: "home", display_frontend: true}, {...app, name: "fre3nderscreen", display_frontend: true}];
  state.display = {active: "fre3nderscreen", apps: state.installed};
  await appsLoad();
  await appsAction("display/select", {name: "doom"});
  assert(el("operation").matches(":modal"), "display switch must keep the operation modal");
  assert(el("operation").dataset.state === "running", "display switch must wait for the receipt");
  assert(el("operation-title").textContent.includes("doom"), "running switch must name doom");
  el("operation-details").querySelector("summary").click();
  const running = JSON.parse(el("operation-result").textContent);
  assert(running.state === "running" && running.operation === "display-select", "live receipt must be visible");
  state.execution = {...state.execution, state: "failed", error: {code: "package-rejected",
    message: 'Display frontend "doom" failed to start (status: startup-failed; service status not confirmed). Previous display "fre3nderscreen" restored.'}};
  await new Promise((resolve) => setTimeout(resolve, 1400));
  assert(el("operation").dataset.state === "error", "failed start must show an error modal");
  assert(el("operation-title").textContent.includes('Display frontend "doom" failed to start'), "error must identify the failed display");
  const red = getComputedStyle(el("operation-status")).borderTopColor.match(/\d+/g).map(Number);
  assert(red[0] > red[1], "failed display start must be red");
  assert(el("operation-details").open, "failure must preserve expanded details");
  assert(el("operation-result").textContent.includes("startup-failed"), "technical runtime status must be visible");
  assert(el("operation-result").textContent.includes("restored"), "recovery outcome must be visible");
  assert(el("operation-result").textContent === el("result").textContent, "modal and page details must match");
  assert(el("display-active").textContent === "fre3nderscreen", "restored selection must be rendered");
  assert(!el("frontend-error").hidden && el("frontend-error").textContent.includes("startup-failed"), "local error box must agree");
  assert(el("installed-success").hidden && el("package-success").hidden, "failed start must not show success");
  assert(posts === 1, "failure must not submit another operation");
  el("operation-close").click();
  // Retrying a selected but failed frontend must be possible in Maintenance.
  state.display.active = "doom";
  displayRunning = false;
  await appsLoad();
  assert(!el("display-list").querySelector("button").disabled, "selected frontend must support a checked retry");
  document.getElementById("browser-result").textContent = "PASS";
})().catch((error) => { document.getElementById("browser-result").textContent = "FAIL: " + error.stack; });
'''

DISPLAY_BUTTONS_SCENARIO = r'''
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const el = (name) => document.getElementById("apps-" + name);
  const buttons = () => el("display-list").querySelectorAll("button");
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
  document.getElementById("apps-view").hidden = false;
  state.display = {active: "doom", apps: [app, {...app, name: "fre3nderscreen"}]};
  await appsLoad();
  assert(displayStatusReads === 1 && posts === 0, "initial state must be confirmed through detail API");
  assert(buttons()[0].textContent === "Selected" && buttons()[0].disabled, "confirmed active selection must be disabled");
  assert(buttons()[1].textContent === "Select" && !buttons()[1].disabled, "other frontend must remain selectable");

  displayRunning = false;
  await appsLoad();
  assert(buttons()[0].textContent === "Retry start" && !buttons()[0].disabled, "non-running selection must support retry");
  buttons()[0].click(); await tick();
  assert(posts === 1 && state.execution.operation === "display-select" && state.execution.name === "doom", "retry must use existing display/select operation");
  assert(Array.from(buttons()).every((button) => button.disabled), "running operation must block competing actions");
  state.execution = {...state.execution, state: "failed", error: {message: 'Display frontend "doom" failed to start (startup-failed).'}};
  await appsLoad();
  assert(buttons()[0].textContent === "Retry start" && !buttons()[0].disabled, "failed retry must remain retryable");
  assert(el("operation").dataset.state === "error", "failed retry must retain the red modal");
  el("operation-close").click();

  buttons()[0].click(); await tick();
  displayRunning = true;
  state.execution = {...state.execution, state: "succeeded", result: {display: {active: "doom"}}};
  await appsLoad();
  assert(buttons()[0].textContent === "Selected" && buttons()[0].disabled, "successful retry must be confirmed and disabled");
  el("operation-close").click();

  rejectDisplayStatus = true;
  await appsLoad();
  assert(buttons()[0].textContent === "Check status" && !buttons()[0].disabled, "unknown status must not claim readiness");
  assert(!el("frontend-error").hidden, "failed status query must be visible");
  const previousReads = displayStatusReads;
  const previousPosts = posts;
  rejectDisplayStatus = false;
  buttons()[0].click(); await tick();
  assert(displayStatusReads === previousReads + 1 && posts === previousPosts, "checking status must not start a display");
  assert(buttons()[0].textContent === "Selected" && buttons()[0].disabled, "status recovery must confirm readiness");
  assert(el("frontend-error").hidden, "new status check must clear the old status error");
  document.getElementById("browser-result").textContent = "PASS";
})().catch((error) => { document.getElementById("browser-result").textContent = "FAIL: " + error.stack; });
'''


REPOSITORY_SCENARIOS = r'''
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const el = (name) => document.getElementById("apps-" + name);
  const card = () => el("installed").querySelector(".app-entry");
  document.getElementById("apps-view").hidden = false;
  await appsLoad();
  assert(el("repository").textContent.includes("availability is unknown"), "older API must leave availability unknown");
  state.repository = {
    availability: "checked", configuration: "configured", check: "ok", error: null,
    identity: {name: "Fixture repository"}, revision: 7, last_success: "2026-10-20T10:00:00+00:00",
    updates: [{name: "doom", installed: {version: "1.0", release_serial: 1},
      offered: {version: "0.5", release_serial: 2, channel: "testing"}, publisher: {id: "trusted"}}]
  };
  await appsLoad();
  assert(card().textContent.includes("Update: 0.5 (testing)"), "API-selected version and channel must be shown without comparison");
  assert(el("repository").textContent.includes("check succeeded"), "successful check must be explicit");
  assert(el("repository").textContent.includes("Fixture repository"), "repository identity must be visible");
  assert(el("repository").textContent.includes("Last successful check: 2026-10-20"), "snapshot time must be visible");
  assert(card().querySelectorAll("button").length === 3, "repository offers must not add actions");
  Array.from(card().querySelectorAll("button")).find((button) => button.textContent === "Update").click();
  assert(posts === 0 && el("message").textContent.includes("choose its new signed .fre3app"), "manual Update must still request a local package");
  state.repository.availability = "cached";
  state.repository.check = "error";
  state.repository.error = {message: "Network unreachable"};
  await appsLoad();
  assert(card().textContent.includes("Cached information"), "cached offer must be marked beside the app");
  assert(el("repository").textContent.includes("check failed. Showing cached information"), "cached data must not claim success");
  assert(el("repository").textContent.includes("Network unreachable"), "check failure must be visible");
  state.repository.updates = [];
  await appsLoad();
  assert(!el("repository").textContent.includes("No updates offered"), "empty cache must not confirm no updates");
  state.repository.availability = "unavailable";
  await appsLoad();
  assert(el("repository").textContent.includes("availability is unknown"), "unavailable repository must remain unknown");
  assert(!card().textContent.includes("Update:"), "unavailable repository must not show offers");
  state.repository.availability = "checked";
  state.repository.check = "ok";
  state.repository.error = null;
  await appsLoad();
  assert(el("repository").textContent.includes("check succeeded. No updates offered."), "empty successful check must be distinguishable");
  const literal = '<img src="x" onerror="window.bad=true">';
  state.repository.identity.name = literal;
  state.repository.updates = [{name: "doom", offered: {version: literal, channel: "stable"}}];
  await appsLoad();
  assert(el("repository").textContent.includes(literal) && card().textContent.includes(literal), "repository text must be displayed literally");
  assert(!el("installed").querySelector("img") && !el("repository").querySelector("img"), "repository data must not become markup");
  assert(posts === 0 && !el("operation").open, "repository rendering must never start an operation");
  document.getElementById("browser-result").textContent = "PASS";
})().catch((error) => { document.getElementById("browser-result").textContent = "FAIL: " + error.stack; });
'''


@unittest.skipUnless(CHROMIUM, "Chromium is required for the DOM/CSS regression")
class MaintenanceAppsBrowserTests(unittest.TestCase):
    def test_repository_updates_and_optional_availability(self):
        for size in ("900,650", "360,480"):
            with self.subTest(window_size=size):
                self.run_browser(REPOSITORY_SCENARIOS, size)

    def test_confirmed_removal_and_local_messages(self):
        self.run_browser(SCENARIOS)

    def test_operation_modal_and_scrollable_details(self):
        for size in ("900,650", "360,480"):
            with self.subTest(window_size=size):
                self.run_browser(MODAL_SCENARIOS, size)

    def test_display_start_failure_and_restoration_in_modal(self):
        self.run_browser(DISPLAY_SCENARIO)

    def test_display_selection_buttons_follow_checked_runtime(self):
        self.run_browser(DISPLAY_BUTTONS_SCENARIO)

    def run_browser(self, scenarios, window_size="900,650"):
        with tempfile.TemporaryDirectory(prefix="fre3nder-apps-browser-") as tmp:
            root = Path(tmp)
            for name in ("apps.js", "maintenance.css"):
                shutil.copyfile(WEB / name, root / name)
            html = (WEB / "index.html").read_text().replace(
                '<script src="maintenance.js"></script>', f"<script>{FIXTURE}</script>"
            ).replace("</body>", f'<pre id="browser-result">PENDING</pre><script>{scenarios}</script></body>')
            (root / "index.html").write_text(html)
            result = subprocess.run(
                [CHROMIUM, "--headless", "--no-sandbox", "--disable-gpu", "--disable-background-networking",
                 f"--window-size={window_size}",
                 f"--user-data-dir={root / 'profile'}", "--virtual-time-budget=5000", "--dump-dom",
                 (root / "index.html").as_uri()],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<pre id="browser-result">PASS</pre>', result.stdout, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
