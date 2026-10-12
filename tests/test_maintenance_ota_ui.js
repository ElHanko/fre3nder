"use strict";

// Host-only browser/API fixtures. No network or target operations are performed.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../configs/x2000/rootfs-overlay/usr/share/fre3nder/web-root/maintenance/maintenance.js"), "utf8");
const packageId = "a".repeat(32);
const transactionId = "b".repeat(32);
const digest = "d".repeat(64);
const copy = (value) => JSON.parse(JSON.stringify(value));
const flush = () => new Promise((resolve) => setImmediate(resolve));

class Element {
  constructor(tag = "div") {
    this.tag = tag; this.children = []; this.listeners = {}; this.value = "";
    this.dataset = {}; this.classList = { toggle() {} };
  }
  replaceChildren() { this.children = []; this.value = ""; }
  append(...children) {
    for (const child of children) {
      this.children.push(child);
      if (this.tag === "select" && this.children.length === 1) this.value = child.value;
    }
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}

function backend() {
  const api = {
    calls: [], requests: [], headers: [], counter: 0, confirmation: [], approve: true,
    fail: null, loseResponse: null, hold: null, held: null, reachable: true,
    preflight: {
      api_version: 1, ok: true, operation: "preflight",
      package: { version: "new", status: "valid" },
      runtime: { installed_version: "old", active_slot: "A" }, target: { slot: "B" },
      backup_offer: {
        home: { offered: true, required: false, targets: ["usb"] },
        sys: { offered: true, required: false, targets: ["home", "usb"] },
      },
    },
    state: {
      core: { transaction: null, activation: null, known_good: null, busy: false },
      execution: null, packages: [{ id: packageId, size: 1024 }],
      storage: { available_bytes: 256 * 1024 * 1024, reserve_bytes: 32 * 1024 * 1024 },
    },
  };
  api.finish = (job) => {
    if (api.fail === job.operation) {
      api.state.execution = { ...job, state: "failed", error: { message: `fixture ${job.operation} failure`, code: "ota-operation-failed" } };
      return;
    }
    const operation = job.operation;
    let result = { api_version: 1, ok: true, operation };
    if (["verify", "preflight", "backup-plan"].includes(operation)) result = { ...copy(api.preflight), operation };
    if (operation === "backup") {
      const selection = { complete: true };
      const backups = { complete: true };
      for (const role of ["home", "sys"]) {
        selection[role] = { selected: job[role] !== "none", target: job[role] === "none" ? null : job[role] };
        backups[role] = { ...selection[role], ...(selection[role].selected ? { archive: `fixture-${role}.tar`, size: 10, sha256: digest, verified: true } : {}) };
      }
      api.state.core.transaction = {
        api_version: 1, transaction_id: transactionId, state: "awaiting-confirmation",
        package: { path: `/ota/packages/${packageId}.ota`, version: api.preflight.package.version, sha256: digest, size: 1024 },
        runtime: copy(api.preflight.runtime), target: copy(api.preflight.target),
        backup_selection: selection, backup_result: backups,
      };
      result.confirmation = { transaction_id: transactionId };
    }
    const transitions = {
      confirm: ["awaiting-confirmation", "confirmed"],
      write: ["confirmed", "written-awaiting-readback"],
      readback: ["written-awaiting-readback", "readback-verified"],
      "prepare-activation": ["readback-verified", "activation-prepared"],
    };
    if (transitions[operation]) {
      const transaction = api.state.core.transaction;
      assert.equal(job.transaction_id, transaction.transaction_id);
      assert.equal(transaction.state, transitions[operation][0]);
      if (operation === "write") {
        for (const role of ["home", "sys"]) if (transaction.backup_result[role].selected) assert.equal(transaction.backup_result[role].verified, true);
      }
      transaction.state = transitions[operation][1];
      result.transaction = { transaction_id: transactionId, state: transaction.state };
    }
    if (operation === "reboot") {
      assert.equal(api.state.core.transaction.state, "activation-prepared");
      result.state = "reboot-requested";
      result.transaction_id = transactionId;
    }
    api.state.execution = { ...job, state: "succeeded", result };
  };
  api.start = (operation, payload) => {
    api.calls.push({ operation, ...payload });
    const job = { id: (++api.counter).toString(16).padStart(32, "0"), state: "running", operation, ...payload };
    api.state.execution = copy(job);
    if (api.hold === operation) api.held = job;
    else api.finish(job);
    return job;
  };
  api.release = () => { const job = api.held; api.held = null; api.hold = null; api.finish(job); };
  api.ready = () => {
    api.state.execution = { id: "0".repeat(32), state: "succeeded", operation: "preflight", package_id: packageId, result: copy(api.preflight) };
  };
  return api;
}

function browser(api, storage = new Map()) {
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, new Element(["ota-package", "ota-home", "ota-sys"].includes(id) ? "select" : "div"));
    return elements.get(id);
  };
  const timers = new Map();
  const events = {};
  let timerId = 0;
  const context = vm.createContext({
    document: { getElementById: get, createElement: (tag) => new Element(tag), querySelectorAll: () => [] },
    window: {
      location: { hash: "#updates" }, addEventListener: (name, fn) => { events[name] = fn; },
      confirm: (message) => { api.confirmation.push(message); return api.approve; },
      sessionStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    },
    setTimeout: (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; },
    clearTimeout: (id) => timers.delete(id),
    fetch: async (url, options = {}) => {
      api.requests.push({ url, method: options.method || "GET" });
      // Tests explicitly control pairing; leave automatic overview initialization pending.
      if (!url.includes("/ota/")) return new Promise(() => {});
      if (!api.reachable) throw new Error("Maintenance unreachable");
      const operation = url.split("/").pop();
      if (options.method === "POST") {
        assert.equal(options.credentials, "same-origin");
        assert.equal(options.headers["X-Fre3nder-CSRF"], "fixture-csrf");
        api.headers.push(options.headers);
        if (operation === "reboot" && api.onReboot) api.onReboot();
        if (api.rejectReboot && operation === "reboot") {
          return { ok: false, status: api.rejectReboot, json: async () => ({ api_version: 1, ok: false, error: { message: "Restart request was not accepted" } }) };
        }
        if (api.disconnectBeforeReboot && operation === "reboot") throw new Error("request connection lost");
        if (api.invalidRebootResponse && operation === "reboot") {
          return { ok: false, status: 502, json: async () => { throw new Error("gateway unavailable"); } };
        }
        const job = api.start(operation, JSON.parse(options.body));
        if (operation === "reboot" && api.disconnectAfterReboot) api.reachable = false;
        if (api.loseResponse === operation) throw new Error("response connection lost");
        return { ok: true, status: 202, json: async () => ({ api_version: 1, ok: true, execution: job }) };
      }
      if (api.expireAfterReboot && api.calls.some((call) => call.operation === "reboot")) {
        return { ok: false, status: 401, json: async () => ({ api_version: 1, ok: false, error: { message: "Pairing required after boot" } }) };
      }
      return { ok: true, status: 200, json: async () => ({ api_version: 1, ok: true, ota: copy(api.state) }) };
    },
    XMLHttpRequest: class {
      constructor() { this.upload = {}; this.headers = {}; }
      open(method, url) { assert.equal(method, "POST"); assert.ok(url.endsWith("/ota/upload")); }
      setRequestHeader(name, value) { this.headers[name] = value; }
      send(file) {
        assert.equal(this.headers["X-Fre3nder-CSRF"], "fixture-csrf");
        api.sentFile = file;
        api.calls.push({ operation: "upload" });
        this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
        assert.equal(get("ota-upload-progress").value, 50);
        this.status = 202; this.response = { api_version: 1, ok: true, execution: api.start("verify", { package_id: packageId }) };
        this.onload();
      }
    },
  });
  vm.runInContext(source, context);
  vm.runInContext('csrfToken = "fixture-csrf"', context);
  return {
    context, get, storage, events,
    call: (expression) => vm.runInContext(expression, context),
    load: () => vm.runInContext("loadOta()", context),
    choices: (home, sys) => { get("ota-home").value = home; get("ota-sys").value = sys; vm.runInContext("renderOta()", context); },
    tick: async (ms) => {
      for (const [id, timer] of timers) if (timer.ms === ms) { timers.delete(id); await timer.callback(); break; }
      await flush();
    },
  };
}
const operations = (api) => api.calls.map((call) => call.operation);
const sequence = ["backup-plan", "backup", "confirm", "write", "readback", "prepare-activation", "reboot"];
let passed = 0;
async function test(name, run) { await run(); ++passed; console.log(`PASS: ${name}`); }

async function main() {
  await test("upload automatically verifies and checks compatibility", async () => {
    const api = backend(); const ui = browser(api); await ui.load();
    const file = { name: "fixture.ota", size: 1024 }; ui.get("ota-file").files = [file];
    await ui.get("ota-upload-form").listeners.submit({ preventDefault() {} });
    assert.equal(api.sentFile, file);
    assert.deepEqual(operations(api), ["upload", "verify", "preflight"]);
    for (const step of ["upload", "verify", "preflight"]) assert.equal(ui.get(`ota-package-${step}`).textContent, "Done");
    assert.equal(ui.get("ota-update").disabled, true); // Both backup choices remain explicit.
  });
  await test("staged package has one check action and same-version warning", async () => {
    const api = backend(); api.preflight.package.version = "old";
    const ui = browser(api); await ui.load(); await ui.call("checkPackage()");
    assert.deepEqual(operations(api), ["verify", "preflight"]);
    assert.equal(ui.get("ota-reinstall").hidden, false);
    assert.deepEqual(ui.get("ota-home").children.map((option) => option.value), ["", "usb", "none"]);
    ui.choices("none", ""); assert.equal(ui.get("ota-update").disabled, true);
    ui.choices("none", "none"); assert.equal(ui.get("ota-update").disabled, false);
  });
  for (const mode of ["development", "release", "unknown", undefined]) {
    await test(`same-version ${mode || "missing mode"} notice agrees with confirmation and permits installation`, async () => {
      const api = backend(); api.preflight.package.version = "old";
      if (mode) api.preflight.package.artifact_mode = mode;
      const ui = browser(api); await ui.load();
      ui.get("ota-file").files = [{ name: "fixture.ota", size: 1024 }];
      await ui.get("ota-upload-form").listeners.submit({ preventDefault() {} });
      const notice = ui.get("ota-reinstall").textContent;
      assert.equal(ui.get("ota-reinstall").hidden, false);
      if (mode === "development") {
        assert.equal(notice, "Development build: The version numbers match, but the builds may differ. The selected package will be installed.");
      } else {
        assert.equal(notice, "The version numbers match. The selected package will be installed again; matching version numbers do not establish identical builds.");
      }
      ui.choices("none", "none"); assert.equal(ui.get("ota-update").disabled, false);
      await ui.call("runUpdate()");
      assert.ok(api.confirmation[0].includes(notice));
      assert.ok(api.confirmation[0].includes("old → old"));
      assert.deepEqual(operations(api), ["upload", "verify", "preflight", ...sequence]);
    });
  }
  await test("no-backup update runs every Core operation after one confirmation", async () => {
    const api = backend(); api.ready(); const ui = browser(api); await ui.load(); ui.choices("none", "none");
    api.onReboot = () => {
      assert.equal(ui.get("ota-reboot-view").hidden, false);
      assert.equal(ui.get("ota-reboot-status").textContent, "Sending printer restart request");
      assert.equal(ui.get("ota-progress-activate").textContent, "Done");
    };
    await ui.call("runUpdate()");
    assert.deepEqual(operations(api), sequence);
    assert.equal(api.confirmation.length, 1);
    for (const text of ["old", "new", "slot A", "slot B", "WARNING", "HOME", "SYS", "Kernel", "RootFS", "restarted"]) assert.ok(api.confirmation[0].includes(text));
    assert.equal(ui.get("ota-progress-backups").textContent, "Skipped");
    assert.equal(ui.get("ota-progress-activate").textContent, "Done");
    assert.equal(ui.get("ota-workflow").hidden, true);
    assert.equal(ui.get("ota-reboot-view").hidden, false);
    assert.equal(ui.get("ota-reboot-status").textContent, "Printer restart requested");
    assert.ok(ui.get("ota-reboot-message").textContent.includes("instructed to restart"));
    const requests = api.requests.length;
    api.reachable = false;
    await ui.tick(2000); await ui.load(); ui.events.pageshow(); await ui.call("runUpdate()");
    assert.equal(api.requests.length, requests);
    const reloaded = browser(api, ui.storage); await reloaded.load(); reloaded.events.pageshow();
    assert.equal(api.requests.length, requests);
    assert.equal(reloaded.get("ota-reboot-status").textContent, "Printer restart requested");
    assert.deepEqual(operations(api), sequence);
    assert.ok(!ui.storage.get("fre3nder-ota-receipt").includes("fixture-csrf"));
  });
  await test("selected backups are verified before the system write", async () => {
    const api = backend(); api.ready(); const ui = browser(api); await ui.load(); ui.choices("usb", "home");
    await ui.call("runUpdate()");
    assert.deepEqual(operations(api), sequence);
    assert.equal(api.calls[1].home, "usb"); assert.equal(api.calls[1].sys, "home");
    assert.equal(api.state.core.transaction.backup_result.home.verified, true);
    assert.equal(api.state.core.transaction.backup_result.sys.verified, true);
    assert.equal(ui.get("ota-progress-backups").textContent, "Done");
  });
  await test("declined confirmation starts no Core operation", async () => {
    const api = backend(); api.ready(); api.approve = false;
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.deepEqual(api.calls, []);
  });
  await test("new local file cannot accidentally update the previously checked package", async () => {
    const api = backend(); api.ready(); const ui = browser(api); await ui.load(); ui.choices("none", "none");
    ui.get("ota-file").files = [{ name: "replacement.ota", size: 1024 }];
    ui.get("ota-file").listeners.change();
    assert.equal(ui.get("ota-update").disabled, true);
    await ui.call("runUpdate()"); assert.deepEqual(api.calls, []);
  });
  await test("every failed update phase stops all subsequent operations", async () => {
    for (const operation of sequence) {
      const api = backend(); api.ready(); api.fail = operation;
      const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
      assert.deepEqual(operations(api), sequence.slice(0, sequence.indexOf(operation) + 1));
      assert.ok(ui.get("ota-error").textContent.includes(`fixture ${operation} failure`));
      await ui.load(); assert.equal(api.calls.length, sequence.indexOf(operation) + 1);
    }
  });
  await test("failed compatibility check supports targeted read-only retry", async () => {
    const api = backend(); api.fail = "preflight"; const ui = browser(api); await ui.load();
    await ui.call("checkPackage()"); assert.equal(ui.get("ota-update").disabled, true);
    assert.equal(ui.get("ota-check").textContent, "Retry compatibility check");
    api.fail = null; await ui.call("checkPackage()");
    assert.deepEqual(operations(api), ["verify", "preflight", "preflight"]);
  });
  await test("double click cannot start a second sequence", async () => {
    const api = backend(); api.ready(); api.hold = "backup-plan";
    const ui = browser(api); await ui.load(); ui.choices("none", "none");
    const first = ui.call("runUpdate()"); const second = ui.call("runUpdate()"); await flush();
    assert.deepEqual(operations(api), ["backup-plan"]);
    assert.equal(api.confirmation.length, 1);
    api.release(); await ui.tick(1000); await first; await second;
    assert.deepEqual(operations(api), sequence);
  });
  await test("reload waits for running write and requires explicit continuation", async () => {
    const api = backend(); api.ready(); api.hold = "write";
    const old = browser(api); await old.load(); old.choices("none", "none");
    const running = old.call("runUpdate()"); await flush();
    assert.equal(api.state.execution.operation, "write");
    old.events.pagehide();
    const reloaded = browser(api, old.storage); await reloaded.load();
    assert.equal(reloaded.get("ota-update").disabled, true);
    const before = api.calls.length;
    api.release(); await old.tick(1000); await running; await reloaded.load();
    assert.equal(api.calls.length, before); // Status restoration submits nothing.
    assert.equal(reloaded.get("ota-progress-write").textContent, "Done");
    assert.equal(reloaded.get("ota-update").textContent, "Continue update");
    api.approve = false; await reloaded.call("runUpdate()"); assert.equal(api.calls.length, before);
    api.approve = true; await reloaded.call("runUpdate()");
    assert.deepEqual(operations(api), sequence);
    assert.equal(api.calls.filter((call) => call.operation === "write").length, 1);
  });
  await test("lost write response is inspected and never repeated automatically", async () => {
    const api = backend(); api.ready(); api.loseResponse = "write";
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.deepEqual(operations(api), sequence.slice(0, 4));
    await ui.load(); assert.equal(ui.get("ota-progress-write").textContent, "Done");
    assert.equal(ui.get("ota-update").disabled, false);
    api.loseResponse = null; await ui.call("runUpdate()");
    assert.deepEqual(operations(api), sequence);
  });
  for (const reload of [false, true]) {
    await test(`same-version continuation uses ${reload ? "neutral wording without cached metadata" : "available development metadata"}`, async () => {
      const api = backend(); api.preflight.package.version = "old";
      api.preflight.package.artifact_mode = "development"; api.ready(); api.fail = "write";
      let ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
      if (reload) { ui.events.pagehide(); ui = browser(api, ui.storage); await ui.load(); }
      const notice = ui.get("ota-reinstall").textContent;
      assert.equal(notice.startsWith("Development build:"), !reload);
      assert.equal(ui.get("ota-reinstall").hidden, false);
      assert.equal(ui.get("ota-update").disabled, false);
      api.fail = null; await ui.call("runUpdate()");
      assert.ok(api.confirmation[1].includes(notice));
      assert.ok(api.confirmation[1].includes("old → old"));
    });
  }
  await test("reload after successful backup plan continues without repeating that plan", async () => {
    const api = backend(); api.ready(); api.hold = "backup-plan";
    const old = browser(api); await old.load(); old.choices("none", "none");
    const pending = old.call("runUpdate()"); await flush(); old.events.pagehide();
    api.release(); await old.tick(1000); await pending;
    const reloaded = browser(api, old.storage); await reloaded.load();
    assert.equal(reloaded.get("ota-update").disabled, false);
    assert.equal(reloaded.get("ota-progress-prepare").textContent, "Done");
    await reloaded.call("runUpdate()"); assert.deepEqual(operations(api), sequence);
    assert.equal(api.calls.filter((call) => call.operation === "backup-plan").length, 1);
  });
  await test("lost reboot response ends without error, polling, pairing or automatic repetition", async () => {
    const api = backend(); api.ready(); api.loseResponse = "reboot";
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.equal(ui.get("ota-error").hidden, true);
    assert.equal(ui.get("ota-reboot-view").hidden, false);
    assert.equal(ui.get("ota-reboot-status").textContent, "Printer restart status unclear");
    assert.ok(ui.get("ota-reboot-message").textContent.includes("Please inspect the printer"));
    assert.equal(api.calls.filter((call) => call.operation === "reboot").length, 1);
    api.reachable = false;
    const requests = api.requests.length;
    await ui.tick(2000); await ui.load(); ui.events.pageshow();
    const reloaded = browser(api, ui.storage); await reloaded.load();
    await reloaded.call("runUpdate()");
    assert.equal(api.requests.length, requests);
    assert.equal(reloaded.get("ota-reboot-status").textContent, "Printer restart status unclear");
    assert.deepEqual(operations(api), sequence);
  });
  await test("unknown execution and expired session cannot advance an update", async () => {
    const api = backend(); api.ready(); const ui = browser(api); await ui.load(); ui.choices("none", "none");
    api.state.execution.state = "unknown"; api.state.execution.error = { message: "outcome unknown" };
    await ui.load(); assert.equal(ui.get("ota-update").disabled, true); await ui.call("runUpdate()");
    assert.deepEqual(api.calls, []);
    api.ready(); await ui.load(); ui.call("renderAuth({authenticated: false})");
    assert.equal(ui.get("ota-update").disabled, true); await ui.call("runUpdate()"); assert.deepEqual(api.calls, []);
  });
  await test("reboot view is prepared before an asynchronous request finishes; reload does not retry it", async () => {
    const api = backend(); api.ready(); api.hold = "reboot";
    const ui = browser(api); await ui.load(); ui.choices("none", "none");
    const pending = ui.call("runUpdate()"); await flush();
    assert.equal(ui.get("ota-reboot-view").hidden, false);
    assert.equal(ui.get("ota-workflow").hidden, true);
    assert.equal(ui.get("ota-reboot-status").textContent, "Sending printer restart request");
    assert.ok(ui.get("ota-reboot-message").textContent.includes("not yet been confirmed"));
    ui.events.pagehide();
    const requests = api.requests.length;
    const reloaded = browser(api, ui.storage); await reloaded.load();
    assert.equal(reloaded.get("ota-reboot-status").textContent, "Printer restart status unclear");
    assert.equal(reloaded.get("ota-update").disabled, true);
    assert.equal(api.requests.length, requests);
    api.release(); await ui.tick(1000); await pending;
    assert.deepEqual(operations(api), sequence);
  });
  await test("session reset during reboot ends neutrally without waiting for re-pairing", async () => {
    const api = backend(); api.ready(); api.expireAfterReboot = true;
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.equal(ui.get("ota-error").hidden, true);
    assert.equal(ui.get("ota-reboot-status").textContent, "Printer restart status unclear");
    assert.equal(ui.get("ota-update").disabled, true);
    assert.equal(api.calls.filter((call) => call.operation === "reboot").length, 1);
    const requests = api.requests.length;
    await ui.tick(2000); await ui.load();
    assert.equal(api.requests.length, requests);
  });
  await test("disconnect after job acceptance leaves the view visible without reconnecting", async () => {
    const api = backend(); api.ready(); api.disconnectAfterReboot = true;
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.equal(ui.get("ota-reboot-view").hidden, false);
    assert.equal(ui.get("ota-reboot-status").textContent, "Printer restart status unclear");
    assert.equal(ui.get("ota-error").hidden, true);
    const requests = api.requests.length;
    await ui.tick(2000); ui.events.pageshow(); await ui.load();
    ui.call("renderAuth({authenticated: true, csrf_token: 'fixture-csrf'})");
    assert.equal(api.requests.length, requests);
    assert.deepEqual(operations(api), sequence);
  });
  await test("rejected reboot offers confirmed continuation without repeating activation", async () => {
    const api = backend(); api.ready(); api.rejectReboot = 502;
    const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
    assert.equal(ui.get("ota-reboot-view").hidden, true);
    assert.equal(ui.get("ota-error").hidden, false);
    assert.equal(ui.get("ota-error").textContent, "Restart request was not accepted");
    await ui.load();
    assert.equal(ui.get("ota-update").textContent, "Continue update");
    assert.equal(ui.get("ota-update").disabled, false);
    api.rejectReboot = null; await ui.call("runUpdate()");
    assert.deepEqual(operations(api), sequence);
    assert.equal(api.confirmation.length, 2);
  });
  for (const failure of ["disconnectBeforeReboot", "invalidRebootResponse"]) {
    await test(`${failure} leaves the restart unconfirmed and performs no automatic retry`, async () => {
      const api = backend(); api.ready(); api[failure] = true;
      const ui = browser(api); await ui.load(); ui.choices("none", "none"); await ui.call("runUpdate()");
      assert.deepEqual(operations(api), sequence.slice(0, -1));
      assert.equal(ui.get("ota-reboot-status").textContent, "Printer restart status unclear");
      assert.equal(ui.get("ota-reboot-view").hidden, false);
      assert.equal(ui.get("ota-error").hidden, true);
      const requests = api.requests.length;
      await ui.tick(2000); await ui.load(); await ui.call("runUpdate()");
      assert.equal(api.requests.length, requests);
    });
  }
  console.log(`Maintenance OTA UX fixtures: ${passed} PASS`);
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
