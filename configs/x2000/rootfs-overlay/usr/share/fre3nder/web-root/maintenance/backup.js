"use strict";

let backupState = null;
let backupTimer = null;
let backupSubmitting = false;
let backupEpoch = 0;
let backupStatusError = false;
const backupElement = (name) => document.getElementById(`backup-${name}`);
const backupError = (message, fromStatus = false) => {
  backupStatusError = Boolean(message) && fromStatus;
  backupElement("error").textContent = message;
  backupElement("error").hidden = !message;
};
const backupTargets = () => {
  const role = backupElement("role").value;
  const choices = backupState && backupState.backup_offer[role].targets || [];
  const select = backupElement("target");
  const previous = select.value;
  select.replaceChildren();
  for (const target of choices) {
    const option = document.createElement("option");
    option.value = target;
    option.textContent = {download: "Browser download", usb: "USB storage", home: "HOME storage"}[target] || target;
    select.append(option);
  }
  select.value = choices.includes(previous) ? previous : choices.includes("download") ? "download" : choices[0] || "";
  const busy = backupSubmitting || Boolean(backupState && backupState.execution && backupState.execution.state === "running");
  backupElement("create").disabled = !csrfToken || busy || !choices.includes(select.value);
  backupElement("role").disabled = busy || !csrfToken;
  select.disabled = busy || !csrfToken || !choices.length;
};
const backupPost = (action, payload) => requestJson(`/fre3nder/api/v1/backup/${action}`, {
  method: "POST", headers: {"Content-Type": "application/json", "X-Fre3nder-CSRF": csrfToken},
  body: JSON.stringify(payload),
});
const backupRender = () => {
  backupTargets();
  const job = backupState && backupState.execution;
  const output = backupElement("result");
  output.textContent = "";
  let message = "Select a role and destination.";
  if (job) {
    if (job.state === "running") message = `Creating and verifying ${job.role.toUpperCase()} backup…`;
    else if (job.state === "succeeded") {
      const result = job.result && job.result.backup_result;
      const archive = result && result[job.role];
      if (result && result.complete === true && archive && archive.verified === true) {
        message = `${job.role.toUpperCase()} backup complete and verified (${job.target}).`;
        output.textContent = `${archive.archive}\n${formatBytes(archive.size)}\nSHA-256: ${archive.sha256}`;
      } else message = "Backup completion could not be verified.";
    } else if (job.state === "discarded") message = "Temporary download backup discarded.";
    else message = job.error && job.error.message || "Backup failed; completion was not confirmed.";
  }
  backupElement("status").textContent = message;
  const downloads = backupElement("downloads");
  downloads.replaceChildren();
  for (const item of backupState && backupState.downloads || []) {
    if (!/^[0-9a-f]{32}$/.test(item.id)) continue;
    const row = document.createElement("div");
    row.className = "backup-download";
    const link = document.createElement("a");
    link.textContent = `Download ${item.role} backup (${formatBytes(item.size)})`;
    link.href = `/fre3nder/api/v1/backup/download?id=${encodeURIComponent(item.id)}`;
    link.setAttribute("download", "");
    const discard = document.createElement("button");
    discard.type = "button";
    discard.className = "secondary-button";
    discard.textContent = "Discard temporary backup";
    discard.disabled = backupSubmitting;
    discard.addEventListener("click", () => backupDiscard(item.id));
    row.append(link, discard);
    downloads.append(row);
  }
};
const backupLoad = async () => {
  if (!csrfToken) return;
  if (backupTimer) clearTimeout(backupTimer);
  backupTimer = null;
  const epoch = ++backupEpoch;
  try {
    const response = await requestJson("/fre3nder/api/v1/backup/status");
    if (epoch !== backupEpoch || !csrfToken) return;
    backupState = response.backup;
    if (backupStatusError) backupError("");
    backupRender();
    if (backupState.execution && backupState.execution.state === "running") {
      backupTimer = setTimeout(backupLoad, 1500);
    }
  } catch (error) {
    if (epoch !== backupEpoch) return;
    backupState = null;
    backupRender();
    backupError(error.message, true);
    if (error.status === 401) renderAuth({authenticated: false});
  }
};
const backupAuthChanged = (authenticated) => {
  ++backupEpoch;
  if (backupTimer) clearTimeout(backupTimer);
  backupTimer = null;
  backupElement("locked").hidden = authenticated;
  backupElement("panel").hidden = !authenticated;
  if (!authenticated) {
    backupState = null;
    backupElement("downloads").replaceChildren();
    backupElement("result").textContent = "";
    backupElement("status").textContent = "";
    backupError("");
  } else if (!document.getElementById("backups-view").hidden) backupLoad();
  backupTargets();
};
const backupDiscard = async (id) => {
  if (!csrfToken || backupSubmitting) return;
  backupSubmitting = true;
  backupError("");
  backupRender();
  try {
    await backupPost("discard", {id});
  } catch (error) {
    backupError(error.message);
    if (error.status === 401) renderAuth({authenticated: false});
  } finally {
    backupSubmitting = false;
    await backupLoad();
  }
};
backupElement("role").addEventListener("change", () => {
  backupElement("target").value = "download";
  backupTargets();
});
backupElement("refresh").addEventListener("click", backupLoad);
backupElement("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!csrfToken || backupSubmitting || backupElement("create").disabled) return;
  const payload = {role: backupElement("role").value, target: backupElement("target").value};
  backupSubmitting = true;
  backupError("");
  backupTargets();
  try {
    const accepted = await backupPost("create", payload);
    if (csrfToken && backupState) {
      backupState.execution = accepted.execution;
      backupRender();
    }
  } catch (error) {
    backupError(error.message + (error.rejected ? "" : " Request outcome unclear; refresh the status before retrying."));
    if (error.status === 401) renderAuth({authenticated: false});
  } finally {
    backupSubmitting = false;
    await backupLoad();
  }
});
backupAuthChanged(Boolean(csrfToken));
