"use strict";

// Host-only DOM/API fixtures; uploads never reach a network or printer.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../configs/x2000/rootfs-overlay/usr/share/fre3nder/web-root/maintenance/apps.js"), "utf8");
const markup = fs.readFileSync(path.join(__dirname, "../configs/x2000/rootfs-overlay/usr/share/fre3nder/web-root/maintenance/index.html"), "utf8");
const declarations = new Map(Array.from(markup.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/g),
  (match) => [match[3], { tag: match[1], hidden: /\bhidden\b/.test(match[2]) }]));
const packageId = "a".repeat(32);
const copy = (value) => JSON.parse(JSON.stringify(value));
const identity = (name) => ({ name, version: "2.0", release_serial: 2, publisher: "trusted", web_frontend: true, display_frontend: false });
const repository = (changes = {}) => ({
  client_installed: true, configuration: "configured", check: "ok", availability: "checked",
  identity: {name: "Fixture repository", key_fingerprint: "c".repeat(64), base_url: "https://repository.example.invalid/"},
  revision: 7, last_success: "2026-10-20T10:00:00+00:00", error: null,
  updates: [{name: "fluidd", installed: {version: "1.0", release_serial: 1},
    offered: {version: "2.0", release_serial: 2, channel: "stable"},
    publisher: {id: "trusted", key_fingerprint: "a".repeat(64)}}],
  ...changes,
});

class Element {
  constructor(tag = "div") {
    this.tag = tag; this.children = []; this.listeners = {}; this.value = "";
    this.open = false; this.dataset = {};
  }
  replaceChildren() { this.children = []; this.textContent = ""; this.value = ""; }
  append(...children) {
    this.children.push(...children);
    if (this.tag === "select" && this.children.length) this.value = this.children[0].value;
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this[name] = value; }
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
}

function browser() {
  const elements = new Map();
  const get = (id) => {
    const find = (element) => element.id === id ? element : element.children.map(find).find(Boolean);
    for (const element of elements.values()) {
      const found = find(element);
      if (found) return found;
    }
    if (!elements.has(id)) {
      const declaration = declarations.get(id);
      assert.ok(declaration, `Missing DOM element: ${id}`);
      const element = new Element(declaration.tag);
      element.hidden = declaration.hidden;
      elements.set(id, element);
    }
    return elements.get(id);
  };
  const api = {
    calls: [], reads: 0, timers: new Map(), confirmations: [], approve: true, counter: 0, uploadedApp: "fluidd",
    detailReads: [], displayRunning: true,
    state: {
      installed: [{ ...identity("fluidd"), version: "1.0", release_serial: 1, storage: "sys" },
        { ...identity("octoapp"), version: "1.0", release_serial: 1, storage: "home" }],
      web: { active: "fluidd" }, display: { active: null, apps: [] },
      packages: [], verified_packages: [], execution: null,
      storage: { available_bytes: 1024 * 1024 * 1024, max_package_bytes: 256 * 1024 * 1024,
        sys: { available_bytes: 64 * 1024 * 1024 }, home: { available_bytes: 1024 * 1024 * 1024 } },
    },
  };
  api.verified = (name) => {
    api.state.packages = [{ id: packageId, size: 12 }];
    api.state.verified_packages = [packageId];
    api.state.execution = { id: String(++api.counter), operation: "verify", state: "succeeded",
      package_id: packageId, result: { package: identity(name) } };
  };
  api.complete = () => {
    const job = api.state.execution;
    if (api.failOperation === job.operation) {
      api.state.execution = { ...job, state: "failed", error: { message: `fixture ${job.operation} failure` } };
      return;
    }
    const item = identity(job.name);
    const result = job.operation === "remove" ? { name: job.name } : { package: item };
    api.state.execution = { ...job, state: "succeeded", result };
    if (!api.noEffect) {
      if (job.operation === "remove") api.state.installed = api.state.installed.filter((app) => app.name !== job.name);
      if (job.operation === "install") api.state.installed.push({ ...item, storage: job.storage });
      if (job.operation === "update") Object.assign(api.state.installed.find((app) => app.name === job.name), item);
    }
    api.state.packages = []; api.state.verified_packages = [];
  };
  const context = vm.createContext({
    document: { getElementById: get, createElement: (tag) => new Element(tag) },
    window: {
      addEventListener() {},
      confirm: (message) => { api.confirmations.push(message); return api.approve; },
    },
    setTimeout(callback) { const id = ++api.counter; api.timers.set(id, callback); return id; },
    clearTimeout(id) { api.timers.delete(id); },
    requestJson: async (url, options = {}) => {
      const operation = url.split("/apps/")[1];
      if (options.method === "POST") {
        assert.equal(options.headers["X-Fre3nder-CSRF"], "fixture-csrf");
        const payload = JSON.parse(options.body);
        api.calls.push({ operation, ...payload });
        if (api.failRequest === operation) {
          const error = new Error(`fixture ${operation} rejection`);
          error.status = api.errorStatus || 409;
          throw error;
        }
        if (api.failOperation === operation) {
          api.state.execution = { id: String(++api.counter), operation: operation.replace("/", "-"), ...payload,
            name: payload.name || api.uploadedApp, state: "failed",
            error: { message: `fixture ${operation} failure` } };
        } else if (operation === "verify") api.verified(api.uploadedApp);
        else if (operation === "discard") {
          api.state.packages = []; api.state.verified_packages = [];
          return { ok: true };
        } else {
          api.state.execution = { id: String(++api.counter), operation: operation.replace("/", "-"), ...payload,
            name: payload.name || api.uploadedApp, state: "running" };
          if (api.deferOperation !== operation) api.complete();
        }
        return { execution: { ...api.state.execution, state: "running" } };
      }
      if (operation.startsWith("detail?name=")) {
        const name = decodeURIComponent(operation.split("=")[1]);
        api.detailReads.push(name);
        if (api.failDetail) throw new Error("fixture display status unavailable");
        if (api.holdDetail) return await api.holdDetail;
        return { app: { ...identity(name), running: api.displayRunning } };
      }
      assert.equal(operation, "status");
      api.reads++;
      if (api.failStatus) throw new Error("fixture status unavailable");
      return { apps: copy(api.state) };
    },
    XMLHttpRequest: class {
      constructor() { this.upload = {}; this.headers = {}; }
      open(method, url) { assert.equal(method, "POST"); assert.ok(url.endsWith("/apps/upload")); }
      setRequestHeader(name, value) { this.headers[name] = value; }
      send(file) {
        assert.equal(this.headers["X-Fre3nder-CSRF"], "fixture-csrf");
        api.calls.push({ operation: "upload", filename: file.name });
        if (api.uploadError) {
          this.status = 507; this.response = { api_version: 1, ok: false, error: { message: "Not enough HOME space" } };
          this.onload(); return;
        }
        api.verified(api.uploadedApp);
        this.status = 202; this.response = { api_version: 1, ok: true, execution: api.state.execution };
        this.onload();
      }
    },
  });
  vm.runInContext('let csrfToken = "fixture-csrf";', context);
  vm.runInContext(source, context);
  const call = (expression) => vm.runInContext(expression, context);
  const buttons = (element) => element.children.flatMap((child) => child.tag === "button" ? [child] : buttons(child));
  const click = (button) => { assert.ok(button); assert.ok(!button.disabled); return button.listeners.click(); };
  return {
    api, get, call, load: () => call("appsLoad()"),
    select: (name) => {
      const card = get("apps-installed").children.find((child) => child.children[0].textContent.startsWith(name + " ·"));
      return click(buttons(card).find((button) => button.textContent === "Update"));
    },
    confirmations: () => buttons(get("apps-verified")),
    confirm: () => click(buttons(get("apps-verified"))[0]),
    cancel: () => click(get("apps-cancel-update")),
    verify: async () => {
      click(get("apps-verify"));
      await new Promise((resolve) => setImmediate(resolve));
    },
    upload: async (name) => {
      api.uploadedApp = name;
      get("apps-file").files = [{ name: name + ".fre3app", size: 12 }];
      await get("apps-upload-form").listeners.submit({ preventDefault() {} });
    },
  };
}

async function testMatchingUpdate() {
  const ui = browser(); await ui.load(); ui.select("fluidd");
  await ui.upload("fluidd");
  assert.equal(ui.confirmations()[0].textContent, "Confirm update");
  assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload"]);
  await ui.confirm();
  assert.deepEqual(ui.api.calls[1], { operation: "update", package_id: packageId, name: "fluidd" });
  assert.equal(ui.call("appsSelectedUpdate"), null);
  assert.equal(ui.get("apps-cancel-update").hidden, true);
}

const installedText = (ui, name) => ui.get("apps-installed").children
  .find((card) => card.children[0].textContent.startsWith(name + " ·"))
  .children.map((child) => child.textContent || "").join("\n");

async function testRepositoryUpdateDisplayAndManualUpdate() {
  const ui = browser();
  ui.api.state.repository = repository();
  await ui.load();
  assert.match(installedText(ui, "fluidd"), /Update: 2\.0 \(stable\)/);
  assert.doesNotMatch(installedText(ui, "octoapp"), /Update:/);
  const status = ui.get("apps-repository").textContent;
  assert.match(status, /check succeeded/);
  assert.match(status, /Fixture repository.*Index revision: 7.*Last successful check: 2026-10-20/);
  assert.equal(ui.api.reads, 1);
  assert.deepEqual(ui.api.calls, []);
  ui.select("fluidd");
  assert.deepEqual(ui.api.calls, [], "manual Update must still ask for a local package");
  assert.match(ui.get("apps-message").textContent, /choose its new signed \.fre3app package/);
  await ui.upload("fluidd");
  await ui.confirm();
  assert.deepEqual(ui.api.calls, [{operation: "upload", filename: "fluidd.fre3app"},
    {operation: "update", package_id: packageId, name: "fluidd"}]);
}

async function testRepositoryCheckedWithoutUpdates() {
  const ui = browser();
  ui.api.state.repository = repository({updates: []});
  await ui.load();
  assert.match(ui.get("apps-repository").textContent, /check succeeded\. No updates offered\./);
  assert.doesNotMatch(installedText(ui, "fluidd"), /Update:/);
  assert.deepEqual(ui.api.calls, []);
  ui.api.state.installed = [];
  await ui.load();
  assert.equal(ui.get("apps-installed").textContent, "No apps installed.");
  assert.match(ui.get("apps-repository").textContent, /No updates offered/);
}

async function testRepositoryCachedOffersRemainExplicit() {
  const ui = browser();
  const value = repository({availability: "cached", check: "error",
    error: {code: "repository-check-failed", message: "Network unreachable"}});
  value.updates[0].offered = {version: "0.5", release_serial: 2, channel: "testing"};
  ui.api.state.repository = value;
  await ui.load();
  assert.match(installedText(ui, "fluidd"), /Update: 0\.5 \(testing\) · Cached information/);
  assert.match(ui.get("apps-repository").textContent, /check failed\. Showing cached information\./);
  assert.match(ui.get("apps-repository").textContent, /Last successful check: 2026-10-20.*Network unreachable/);
  ui.api.state.repository.updates = [];
  await ui.load();
  assert.match(ui.get("apps-repository").textContent, /cached information/);
  assert.doesNotMatch(ui.get("apps-repository").textContent, /No updates offered|check succeeded|up.to.date/i);
  assert.deepEqual(ui.api.calls, []);
}

async function testRepositoryUnavailableAndOlderApi() {
  const ui = browser();
  for (const value of [repository({availability: "unavailable", check: "error",
    error: {message: "Network unreachable"}, last_success: null, revision: null, updates: []}),
    repository({availability: "unavailable", configuration: "unconfigured", check: "disabled", updates: []}), undefined]) {
    if (value) ui.api.state.repository = value;
    else delete ui.api.state.repository;
    await ui.load();
    assert.match(ui.get("apps-repository").textContent, /availability is unknown/);
    assert.doesNotMatch(ui.get("apps-repository").textContent, /No updates offered|check succeeded|up.to.date/i);
    assert.doesNotMatch(installedText(ui, "fluidd"), /Update:/);
    assert.deepEqual(ui.api.calls, []);
  }
  ui.select("fluidd");
  assert.equal(ui.call("appsSelectedUpdate"), "fluidd");
}

async function testRepositoryTextUsesSafeDomOutput() {
  const ui = browser();
  const value = repository();
  const text = '<img src="x" onerror="bad()">';
  value.updates[0].offered.version = text;
  value.identity.name = text;
  ui.api.state.repository = value;
  await ui.load();
  assert.ok(installedText(ui, "fluidd").includes(`Update: ${text} (stable)`));
  assert.ok(ui.get("apps-repository").textContent.includes(text));
  assert.equal(ui.get("apps-repository").children.length, 0);
  assert.deepEqual(ui.api.calls, []);
}

async function testForeignPackage() {
  for (const name of ["octoapp", "newapp"]) {
    const ui = browser(); await ui.load(); ui.select("fluidd");
    await ui.upload(name);
    assert.equal(ui.confirmations().length, 0);
    assert.match(ui.get("apps-verified").children[0].textContent, new RegExp(`fluidd.*${name}`));
    await ui.load();
    assert.equal(ui.confirmations().length, 0);
    assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload"]);
    assert.deepEqual(ui.api.confirmations, []);
    // Selecting a matching package afterwards still permits the chosen update.
    await ui.upload("fluidd");
    assert.equal(ui.confirmations()[0].textContent, "Confirm update");
  }
}

async function testGeneralUpload() {
  for (const [name, operation] of [["newapp", "install"], ["octoapp", "update"]]) {
    const ui = browser(); await ui.load(); await ui.upload(name);
    assert.equal(ui.api.calls.length, 1);
    await ui.confirm();
    assert.equal(ui.api.calls[1].operation, operation);
    if (operation === "update") assert.equal(ui.api.calls[1].name, name);
  }
}

async function testCancelAndRestart() {
  const ui = browser(); await ui.load(); ui.select("fluidd"); await ui.upload("octoapp");
  ui.cancel(); await ui.load();
  assert.equal(ui.call("appsSelectedUpdate"), null);
  assert.equal(ui.confirmations().length, 0);
  await ui.upload("octoapp"); await ui.confirm();
  assert.equal(ui.api.calls.at(-1).name, "octoapp");
  // A completed receipt must not cancel a newly chosen target on a status refresh.
  ui.select("fluidd"); await ui.load();
  assert.equal(ui.call("appsSelectedUpdate"), "fluidd");
  assert.equal(ui.confirmations().length, 0);
}

async function testDeclinedConfirmationAndDiscard() {
  const ui = browser(); await ui.load(); ui.select("fluidd"); await ui.upload("fluidd");
  ui.api.approve = false; await ui.confirm(); await ui.load();
  assert.equal(ui.call("appsSelectedUpdate"), null);
  assert.equal(ui.confirmations().length, 0);
  assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload"]);
  ui.api.approve = true; ui.select("fluidd"); await ui.upload("fluidd");
  await ui.get("apps-discard").listeners.click();
  assert.equal(ui.call("appsSelectedUpdate"), null);
  assert.equal(ui.confirmations().length, 0);
  assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload", "upload", "discard"]);
}

async function testStagedVerificationRespectsNewSelection() {
  const ui = browser(); await ui.load(); await ui.upload("octoapp");
  assert.equal(ui.confirmations()[0].textContent, "Confirm update");
  ui.select("fluidd"); await ui.load();
  assert.equal(ui.confirmations().length, 0);
  await ui.verify();
  assert.equal(ui.confirmations().length, 0);
  assert.match(ui.get("apps-verified").children[0].textContent, /fluidd.*octoapp/);
  ui.select("octoapp"); await ui.verify();
  assert.equal(ui.confirmations()[0].textContent, "Confirm update");
  assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload", "verify", "verify"]);
  await ui.confirm();
  assert.equal(ui.api.calls.at(-1).name, "octoapp");
}

async function testInstallationStorageSelectionAndUpdatePreservation() {
  for (const role of ["sys", "home"]) {
    const ui = browser(); await ui.load(); await ui.upload("newapp");
    assert.equal(ui.get("apps-install-options").hidden, false);
    assert.equal(ui.get("apps-install-storage").value, "sys");
    assert.match(ui.get("apps-install-storage").children[0].textContent, /64\.0 MiB/);
    ui.get("apps-install-storage").value = role;
    await ui.load();
    assert.equal(ui.get("apps-install-storage").value, role);
    await ui.confirm();
    assert.equal(ui.api.calls.at(-1).storage, role);
    assert.match(ui.api.confirmations.at(-1), new RegExp(`Storage: ${role.toUpperCase()}`));
  }
  const ui = browser(); await ui.load(); await ui.upload("octoapp");
  assert.equal(ui.get("apps-install-options").hidden, true);
  assert.match(ui.get("apps-installed").children[1].children[1].textContent, /Storage: HOME/);
  assert.match(ui.get("apps-verified").children[1].textContent, /Storage: HOME \(preserved\)/);
  await ui.confirm();
  assert.equal(ui.api.calls.at(-1).operation, "update");
  assert.equal("storage" in ui.api.calls.at(-1), false);
}

async function testUploadErrorIsLocalAndKeepsFileSelection() {
  const ui = browser(); await ui.load(); ui.api.uploadError = true;
  await ui.upload("newapp");
  assert.equal(ui.get("apps-upload-error").hidden, false);
  assert.match(ui.get("apps-upload-error").textContent, /HOME/);
  assert.equal(ui.get("apps-progress").hidden, true);
  assert.equal(ui.get("apps-file").files[0].name, "newapp.fre3app");
  assert.ok(!ui.get("apps-error").textContent);
  assert.deepEqual(ui.api.calls.map((call) => call.operation), ["upload"]);
}

async function testPackageFailuresAreLocal() {
  for (const [name, operation] of [["newapp", "install"], ["fluidd", "update"], ["fluidd", "verify"]]) {
    const ui = browser(); await ui.load(); await ui.upload(name);
    ui.api.failOperation = operation;
    if (operation === "verify") await ui.verify();
    else await ui.confirm();
    assert.equal(ui.get("apps-package-error").hidden, false);
    assert.match(ui.get("apps-package-error").textContent, new RegExp(operation));
    if (operation !== "verify") assert.match(ui.get("apps-package-error").textContent, new RegExp(name));
    assert.ok(!ui.get("apps-error").textContent);
  }
}

async function testRemovalAndDisplayFailuresAreLocal() {
  for (const asynchronous of [false, true]) {
    const ui = browser(); await ui.load();
    ui.api[asynchronous ? "failOperation" : "failRequest"] = "remove";
    await ui.call("appsRemove(appsState.installed[0])");
    assert.equal(ui.get("apps-remove-error-fluidd").hidden, false);
    assert.match(ui.get("apps-remove-error-fluidd").textContent, /remove/);
    await ui.load();
    assert.equal(ui.get("apps-remove-error-fluidd").hidden, false);
    assert.ok(!ui.get("apps-error").textContent);
  }
  const ui = browser(); await ui.load();
  ui.api.failOperation = "display/select";
  await ui.call('appsAction("display/select", {name: "octoapp"})');
  assert.equal(ui.get("apps-frontend-error").hidden, false);
  assert.ok(!ui.get("apps-error").textContent);
}

async function testSessionFailureRemainsGlobal() {
  const ui = browser(); await ui.load(); await ui.upload("fluidd");
  ui.api.failRequest = "verify"; ui.api.errorStatus = 401;
  await ui.verify();
  assert.equal(ui.get("apps-error").hidden, false);
  assert.ok(!ui.get("apps-package-error").textContent);
}

const installedNames = (ui) => ui.get("apps-installed").children.map((card) => card.children[0].textContent.split(" ·")[0]);
const assertNoSuccess = (ui) => {
  for (const id of ["installed-success", "package-success"]) assert.equal(ui.get(`apps-${id}`).hidden, true);
};
const poll = async (ui) => {
  assert.equal(ui.api.timers.size, 1);
  const [id, callback] = ui.api.timers.entries().next().value;
  ui.api.timers.delete(id);
  await callback();
};

async function testRemovalWaitsForConfirmedBackendState() {
  const ui = browser(); await ui.load();
  ui.api.deferOperation = "remove";
  await ui.call("appsRemove(appsState.installed[0])");
  assert.deepEqual(installedNames(ui), ["fluidd", "octoapp"]);
  assert.match(ui.get("apps-message").textContent, /Removing fluidd…/);
  assertNoSuccess(ui);
  assert.ok(ui.api.timers.size);
  ui.api.complete();
  await poll(ui);
  assert.deepEqual(installedNames(ui), ["octoapp"]);
  assert.equal(ui.get("apps-installed-success").hidden, false);
  assert.equal(ui.get("apps-installed-success").textContent, 'App "fluidd" was removed successfully.');
  assert.equal(ui.get("apps-message").textContent, "");
  assert.equal(ui.api.calls.length, 1);
  assert.equal(ui.api.timers.size, 0);
  assert.equal(ui.api.reads, 3);
}

async function testSuccessRequiresMatchingInstalledState() {
  for (const [name, operation] of [["fluidd", "remove"], ["newapp", "install"], ["fluidd", "update"]]) {
    const ui = browser(); await ui.load();
    ui.api.noEffect = true;
    if (operation === "remove") await ui.call("appsRemove(appsState.installed[0])");
    else { await ui.upload(name); await ui.confirm(); }
    assert.deepEqual(installedNames(ui), ["fluidd", "octoapp"]);
    assertNoSuccess(ui);
    const error = ui.get(operation === "remove" ? "apps-remove-error-fluidd" : "apps-package-error");
    assert.equal(error.hidden, false);
    assert.match(error.textContent, new RegExp(name));
    assert.match(error.textContent, /Package Core.*success.*(still installed|does not match)/);
    assert.doesNotMatch(ui.get("apps-execution").textContent, /succeeded/);
    await ui.load();
    assert.equal(error.hidden, false);
    assertNoSuccess(ui);
  }
}

async function testInstallAndUpdateCompletionMessages() {
  for (const [name, operation, verb] of [["newapp", "install", "installed"], ["fluidd", "update", "updated"]]) {
    const ui = browser(); await ui.load(); await ui.upload(name);
    ui.api.deferOperation = operation;
    await ui.confirm();
    assertNoSuccess(ui);
    assert.match(ui.get("apps-message").textContent, new RegExp(`${operation === "install" ? "Installing" : "Updating"} ${name}`));
    ui.api.complete(); await poll(ui);
    assert.equal(ui.get("apps-package-success").hidden, false);
    assert.equal(ui.get("apps-package-success").textContent, `App "${name}" was ${verb} successfully.`);
    assert.equal(ui.get("apps-package-error").hidden, true);
    assert.ok(installedNames(ui).includes(name));
    assert.match(ui.get("apps-installed").children.find((card) => card.children[0].textContent.startsWith(name + " ·")).children[0].textContent, /2\.0/);
  }
}

async function testUpdateRequiresTheReportedReleaseSerial() {
  const ui = browser(); await ui.load(); await ui.upload("fluidd");
  ui.api.noEffect = true;
  // The display version alone cannot distinguish these two package releases.
  ui.api.state.installed[0].version = "2.0";
  await ui.confirm();
  assertNoSuccess(ui);
  assert.match(ui.get("apps-package-error").textContent, /fluidd.*does not match/);
  assert.equal(ui.api.state.installed[0].release_serial, 1);
}

async function testNewActionClearsOldMessagesAndReceiptsStayDismissed() {
  const ui = browser(); await ui.load(); await ui.upload("newapp");
  ui.api.failOperation = "remove";
  await ui.call("appsRemove(appsState.installed[0])");
  assert.equal(ui.get("apps-remove-error-fluidd").hidden, false);
  assert.match(ui.get("apps-remove-error-fluidd").textContent, /fluidd/);
  // Even a rejected new request must dismiss the previous execution's failure.
  ui.api.failRequest = "verify";
  await ui.verify(); await ui.load();
  assert.equal(ui.get("apps-remove-error-fluidd").hidden, true);
  assert.equal(ui.get("apps-package-error").hidden, false);
  assert.doesNotMatch(ui.get("apps-execution").textContent, /remove/);
  ui.api.failOperation = null; ui.api.failRequest = null;
  await ui.upload("newapp"); await ui.confirm();
  assert.equal(ui.get("apps-package-error").hidden, true);
  assert.equal(ui.get("apps-package-success").hidden, false);
  ui.api.uploadError = true;
  await ui.upload("otherapp");
  assertNoSuccess(ui);
  assert.equal(ui.get("apps-upload-error").hidden, false);
  await ui.load(); assertNoSuccess(ui);
}

async function testUnknownAndStatusFailuresNeverClaimSuccess() {
  const ui = browser(); await ui.load(); ui.api.deferOperation = "remove";
  await ui.call("appsRemove(appsState.installed[0])");
  ui.api.failStatus = true;
  await poll(ui);
  assertNoSuccess(ui);
  assert.deepEqual(installedNames(ui), ["fluidd", "octoapp"]);
  ui.api.failStatus = false;
  ui.api.state.execution = { ...ui.api.state.execution, state: "unknown", error: { message: "outcome unknown" } };
  await poll(ui);
  assertNoSuccess(ui);
  assert.equal(ui.get("apps-error").hidden, true);
  assert.match(ui.get("apps-remove-error-fluidd").textContent, /fluidd.*outcome unknown/);
  assert.equal(ui.api.calls.length, 1);
  assert.equal(ui.api.timers.size, 0);
}

const assertMirroredDetails = (ui) => {
  assert.equal(ui.get("apps-operation-execution").textContent, ui.get("apps-execution").textContent);
  assert.equal(ui.get("apps-operation-result").textContent, ui.get("apps-result").textContent);
};

async function testOperationModalTracksActionsAndKeepsDetailsOpen() {
  for (const [name, operation, progress, verb] of [["newapp", "install", "Installing", "installed"],
    ["fluidd", "update", "Updating", "updated"], ["fluidd", "remove", "Removing", "removed"]]) {
    const ui = browser(); await ui.load();
    if (operation !== "remove") await ui.upload(name);
    ui.api.deferOperation = operation;
    if (operation === "remove") await ui.call("appsRemove(appsState.installed[0])");
    else await ui.confirm();
    const modal = ui.get("apps-operation");
    assert.equal(modal.open, true);
    assert.equal(modal.dataset.state, "running");
    assert.equal(ui.get("apps-operation-title").textContent, `${progress} ${name}…`);
    assert.equal(ui.get("apps-operation-spinner").hidden, false);
    assert.equal(ui.get("apps-operation-close").hidden, true);
    assert.equal(ui.get("apps-operation-details").open, false);
    assertMirroredDetails(ui);
    assert.equal(JSON.parse(ui.get("apps-operation-result").textContent).id, ui.api.state.execution.id);
    let prevented = false;
    modal.listeners.cancel({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    const calls = ui.api.calls.length;
    for (const action of ["install", "update", "remove", "display/disable", "acknowledge"]) {
      await ui.call(`appsAction("${action}", {name: "octoapp"})`);
    }
    await ui.upload("anotherapp");
    assert.equal(ui.api.calls.length, calls);
    ui.get("apps-operation-details").open = true;
    await poll(ui);
    assert.equal(ui.get("apps-operation-details").open, true);
    assertMirroredDetails(ui);
    ui.get("apps-operation-details").open = false;
    ui.get("apps-operation-details").open = true;
    assert.equal(ui.api.calls.length, calls);
    ui.api.complete(); await poll(ui);
    assert.equal(modal.open, true);
    assert.equal(modal.dataset.state, "success");
    assert.equal(ui.get("apps-operation-title").textContent, `App "${name}" was ${verb} successfully.`);
    assert.equal(ui.get("apps-operation-status").className, "app-operation-status success");
    assert.equal(ui.get("apps-operation-spinner").hidden, true);
    assert.equal(ui.get("apps-operation-close").hidden, false);
    assert.equal(ui.get("apps-operation-details").open, true);
    assertMirroredDetails(ui);
    assert.equal(ui.api.calls.length, calls);
    ui.get("apps-operation-close").listeners.click();
    assert.equal(modal.open, false);
    await ui.load();
    assert.equal(modal.open, false);
  }
}

async function testOperationModalShowsFailuresAndFinalDetails() {
  for (const failure of ["receipt", "unknown", "unchanged", "request"]) {
    const ui = browser(); await ui.load();
    if (failure === "request") ui.api.failRequest = "remove";
    else ui.api.deferOperation = "remove";
    await ui.call("appsRemove(appsState.installed[0])");
    if (failure !== "request") {
      ui.get("apps-operation-details").open = true;
      if (failure === "receipt") { ui.api.failOperation = "remove"; ui.api.complete(); }
      if (failure === "unknown") ui.api.state.execution = { ...ui.api.state.execution, state: "unknown", error: { message: "outcome unknown" } };
      if (failure === "unchanged") { ui.api.noEffect = true; ui.api.complete(); }
      await poll(ui);
      assert.equal(ui.get("apps-operation-details").open, true);
    }
    assert.equal(ui.get("apps-operation").open, true);
    assert.equal(ui.get("apps-operation").dataset.state, "error");
    assert.match(ui.get("apps-operation-title").textContent, /fluidd/);
    assert.equal(ui.get("apps-operation-status").className, "app-operation-status error");
    assert.equal(ui.get("apps-operation-spinner").hidden, true);
    assert.equal(ui.get("apps-operation-close").hidden, false);
    assertMirroredDetails(ui);
    assert.ok(ui.get("apps-operation-result").textContent);
    assertNoSuccess(ui);
    ui.get("apps-operation-close").listeners.click();
    assert.equal(ui.get("apps-operation").open, false);
    assert.equal(ui.get("apps-remove-error-fluidd").hidden, false);
  }
}

async function testDisplayStartFailureShowsRedModalAndRestoredSelection() {
  const ui = browser();
  ui.api.state.display = {active: "fre3nderscreen", apps: [identity("fre3nderscreen"), identity("doom")]};
  await ui.load();
  ui.api.deferOperation = "display/select";
  await ui.get("apps-display-list").children[1].children[1].listeners.click();
  assert.equal(ui.get("apps-operation").dataset.state, "running");
  assert.match(ui.get("apps-operation-title").textContent, /display-select doom/);
  assert.equal(JSON.parse(ui.get("apps-operation-result").textContent).state, "running");
  ui.get("apps-operation-details").open = true;
  ui.api.state.execution = { ...ui.api.state.execution, state: "failed", error: {code: "package-rejected",
    message: 'Display frontend "doom" failed to start (status: startup-failed; service status not confirmed). Previous display "fre3nderscreen" restored.'} };
  await poll(ui);
  assert.equal(ui.get("apps-operation").dataset.state, "error");
  assert.equal(ui.get("apps-operation-status").className, "app-operation-status error");
  assert.match(ui.get("apps-operation-title").textContent, /doom.*failed to start.*fre3nderscreen.*restored/);
  assert.equal(ui.get("apps-operation-details").open, true);
  assert.match(ui.get("apps-operation-result").textContent, /startup-failed/);
  assert.match(ui.get("apps-frontend-error").textContent, /startup-failed/);
  assert.equal(ui.get("apps-display-active").textContent, "fre3nderscreen");
  assertMirroredDetails(ui);
  assertNoSuccess(ui);
  assert.equal(ui.api.calls.length, 1);
  // The selected app may be stopped or failed; selecting it again must remain
  // possible. Package Core decides whether a restart is actually necessary.
  ui.get("apps-operation-close").listeners.click();
  ui.api.state.display.active = "doom";
  ui.api.displayRunning = false;
  await ui.load();
  assert.equal(ui.get("apps-display-list").children[1].children[1].disabled, false);
  assert.equal(ui.get("apps-display-list").children[1].children[1].textContent, "Retry start");
}

const displayButton = (ui, index = 0) => ui.get("apps-display-list").children[index].children[1];

async function testDisplayButtonsUseConfirmedRuntimeStatus() {
  const ui = browser();
  ui.api.state.display = {active: "doom", apps: [identity("doom"), identity("fre3nderscreen")]};
  await ui.load();
  assert.deepEqual(ui.api.detailReads, ["doom"]);
  assert.equal(displayButton(ui).textContent, "Selected");
  assert.equal(displayButton(ui).disabled, true);
  assert.equal(displayButton(ui, 1).textContent, "Select");
  assert.equal(displayButton(ui, 1).disabled, false);
  ui.api.displayRunning = false;
  await ui.load();
  assert.equal(displayButton(ui).textContent, "Retry start");
  assert.equal(displayButton(ui).disabled, false);
  ui.api.deferOperation = "display/select";
  await displayButton(ui).listeners.click();
  assert.deepEqual(ui.api.calls, [{operation: "display/select", name: "doom"}]);
  assert.equal(displayButton(ui).disabled, true);
  assert.equal(displayButton(ui, 1).disabled, true);
  ui.api.displayRunning = true;
  ui.api.complete(); await poll(ui);
  assert.equal(displayButton(ui).textContent, "Selected");
  assert.equal(displayButton(ui).disabled, true);
  assert.equal(ui.get("apps-operation").dataset.state, "success");
}

async function testUnknownDisplayStatusChecksWithoutStarting() {
  const ui = browser();
  ui.api.state.display = {active: "doom", apps: [identity("doom"), identity("fre3nderscreen")]};
  ui.api.failDetail = true;
  await ui.load();
  assert.equal(displayButton(ui).textContent, "Check status");
  assert.equal(displayButton(ui).disabled, false);
  assert.match(ui.get("apps-frontend-error").textContent, /doom.*status unavailable/);
  assert.deepEqual(ui.api.calls, []);
  ui.api.failDetail = false;
  await displayButton(ui).listeners.click();
  assert.deepEqual(ui.api.detailReads, ["doom", "doom"]);
  assert.deepEqual(ui.api.calls, []);
  assert.equal(displayButton(ui).textContent, "Selected");
  assert.equal(displayButton(ui).disabled, true);
  assert.equal(ui.get("apps-frontend-error").hidden, true);
}

async function testLateDisplayStatusCannotChangeNewSelection() {
  const ui = browser();
  ui.api.state.display = {active: "doom", apps: [identity("doom"), identity("fre3nderscreen")]};
  let release;
  ui.api.holdDetail = new Promise((resolve) => { release = resolve; });
  const oldLoad = ui.load();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(displayButton(ui).textContent, "Check status");
  ui.api.holdDetail = null;
  ui.api.state.display.active = "fre3nderscreen";
  ui.api.displayRunning = false;
  await ui.load();
  release({app: {...identity("doom"), running: true}});
  await oldLoad;
  assert.equal(displayButton(ui).textContent, "Select");
  assert.equal(displayButton(ui).disabled, false);
  assert.equal(displayButton(ui, 1).textContent, "Retry start");
  assert.equal(displayButton(ui, 1).disabled, false);
  assert.deepEqual(ui.api.calls, []);
}

(async () => {
  for (const test of [testRepositoryUpdateDisplayAndManualUpdate, testRepositoryCheckedWithoutUpdates,
    testRepositoryCachedOffersRemainExplicit, testRepositoryUnavailableAndOlderApi, testRepositoryTextUsesSafeDomOutput,
    testMatchingUpdate, testForeignPackage, testGeneralUpload, testCancelAndRestart,
    testDeclinedConfirmationAndDiscard, testStagedVerificationRespectsNewSelection,
    testInstallationStorageSelectionAndUpdatePreservation, testUploadErrorIsLocalAndKeepsFileSelection,
    testPackageFailuresAreLocal, testRemovalAndDisplayFailuresAreLocal, testSessionFailureRemainsGlobal,
    testRemovalWaitsForConfirmedBackendState, testSuccessRequiresMatchingInstalledState,
    testInstallAndUpdateCompletionMessages, testUpdateRequiresTheReportedReleaseSerial,
    testNewActionClearsOldMessagesAndReceiptsStayDismissed,
    testUnknownAndStatusFailuresNeverClaimSuccess,
    testOperationModalTracksActionsAndKeepsDetailsOpen, testOperationModalShowsFailuresAndFinalDetails,
    testDisplayStartFailureShowsRedModalAndRestoredSelection,
    testDisplayButtonsUseConfirmedRuntimeStatus, testUnknownDisplayStatusChecksWithoutStarting,
    testLateDisplayStatusCannotChangeNewSelection]) {
    await test(); process.stdout.write(`${test.name}: PASS\n`);
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
