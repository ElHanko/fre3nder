"use strict";

// Uses the existing Chromium/DOM fixture runner, with the real Maintenance JS.
const previousFetch = window.fetch;
const backupFixture = {
  backup_offer: {home: {targets: ["download"]}, sys: {targets: ["download", "home"]}},
  execution: null, downloads: [],
};
let rejectBackup = false, lostBackupReply = false, failBackupStatus = false;
const backupCalls = [];
window.fetch = async (path, options = {}) => {
  if (!path.includes("/backup/")) return previousFetch(path, options);
  backupCalls.push({path, options});
  const reply = (value, status = 200) => ({ok: status < 400, status,
    json: async () => ({api_version: 1, ok: status < 400, ...value})});
  if (path.endsWith("/status")) return failBackupStatus
    ? reply({error: {message: "fixture temporary status failure"}}, 503)
    : reply({backup: JSON.parse(JSON.stringify(backupFixture))});
  if (options.headers["X-Fre3nder-CSRF"] !== "fixture-csrf") throw new Error("Missing CSRF");
  const payload = JSON.parse(options.body);
  if (rejectBackup) return reply({error: {message: "fixture operation conflict", code: "backup-busy"}}, 409);
  if (path.endsWith("/create")) {
    const job = {id: "a".repeat(32), state: "running", operation: "create", ...payload};
    backupFixture.execution = job;
    if (lostBackupReply) throw new Error("fixture lost reply");
    return reply({execution: job}, 202);
  }
  if (path.endsWith("/discard")) {
    backupFixture.downloads = backupFixture.downloads.filter((item) => item.id !== payload.id);
    backupFixture.execution.state = "discarded";
    return reply({discarded: payload.id});
  }
  throw new Error("Unexpected backup API route");
};

(async () => {
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
  const submit = async () => {
    backupElement("form").dispatchEvent(new Event("submit", {cancelable: true}));
    await flush(); await flush();
  };
  try {
    await flush(); await backupLoad();
    assert(!document.getElementById("backups-view").hidden, "Backups navigation");
    assert(document.getElementById("updates-view").hidden, "Independent OTA panel");
    assert(backupElement("target").value === "download", "Default browser download");
    assert(!backupElement("create").disabled, "HOME without USB");
    assert(backupElement("target").options.length === 1, "Only API choices offered");
    const statusCalls = () => backupCalls.filter((call) => call.path.endsWith("/status")).length;
    const beforeRender = statusCalls();
    renderNavigation(); renderNavigation();
    await flush();
    assert(statusCalls() === beforeRender, "Rerendering Backups must not reload status");
    window.location.hash = "#overview";
    renderNavigation();
    window.location.hash = "#backups";
    renderNavigation();
    await flush();
    assert(statusCalls() === beforeRender + 1, "Entering Backups reloads status once");
    backupElement("role").value = "sys";
    backupElement("role").dispatchEvent(new Event("change"));
    assert(backupElement("target").options.length === 2, "SYS HOME option");
    backupFixture.backup_offer.sys.targets.push("usb");
    await backupLoad();
    assert(backupElement("target").options.length === 3, "USB becomes available");
    await submit();
    assert(backupElement("create").disabled, "Busy prevents duplicate creates");
    assert(backupElement("status").textContent.includes("verifying"), "Progress message");
    assert(backupTimer !== null, "Running backup keeps status polling");
    const job = backupFixture.execution;
    const archive = {role: "SYS", target: "download", selected: true, verified: true,
      archive: "/home/.tmp/backup/job-fixture/fixture.tar", size: 10240, sha256: "b".repeat(64)};
    job.state = "succeeded";
    job.result = {backup_result: {complete: true, sys: archive}};
    backupFixture.downloads.push({id: job.id, ...archive});
    await backupLoad();
    assert(backupElement("status").textContent.includes("complete and verified"), "Verified completion");
    const link = backupElement("downloads").querySelector("a");
    assert(link.getAttribute("href") === `/fre3nder/api/v1/backup/download?id=${job.id}`, "Server ID link");
    assert(link.hasAttribute("download"), "Normal browser streaming download");
    assert(document.documentElement.scrollWidth <= innerWidth, "Backup page fits viewport");
    failBackupStatus = true;
    await backupLoad();
    assert(!backupElement("error").hidden, "Status failure is visible");
    assert(backupElement("downloads").children.length === 0, "Failed status clears stale controls");
    assert(backupElement("create").disabled, "Unknown status cannot start another job");
    failBackupStatus = false;
    await backupLoad();
    assert(backupElement("error").hidden, "Recovered status clears its stale error");
    assert(backupElement("downloads").querySelector("a"), "Repeated download remains available");
    backupElement("downloads").querySelector("button").click();
    await flush(); await flush();
    assert(backupElement("downloads").children.length === 0, "Explicit discard");
    rejectBackup = true;
    await submit();
    assert(backupElement("error").textContent.includes("conflict"), "Show operation conflict");
    rejectBackup = false; lostBackupReply = true;
    await submit();
    assert(backupElement("error").textContent.includes("outcome unclear"), "Lost reply is not success");
    backupFixture.execution.state = "failed";
    backupFixture.execution.error = {message: "fixture checksum failure"};
    await backupLoad();
    assert(backupElement("status").textContent.includes("checksum failure"), "Failure is not completion");
    renderAuth({authenticated: false});
    assert(backupElement("panel").hidden, "Lock hides private results");
    assert(backupElement("downloads").children.length === 0, "Lock clears download links");
    assert(!fixture.errors.length, fixture.errors.join("; "));
    document.getElementById("browser-result").textContent = "PASS";
  } catch (error) {
    document.getElementById("browser-result").textContent = `FAIL: ${error.stack}`;
  }
})();
