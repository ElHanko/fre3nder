"use strict";

// Shares the paired browser session with maintenance.js. No credentials persist.
const appsRoot = "/fre3nder/api/v1/apps/";
const appsEl = (name) => document.getElementById(`apps-${name}`);
let appsState = null;
let appsVerified = null;
let appsBusy = false;
let appsSubmitting = false;
let appsPoll = null;
let appsSelectedUpdate = null;
let appsCompletedExecution = null;
const appsErrors = new Map();

const appsCloseOperation = () => { if (appsEl("operation").open) appsEl("operation").close(); };
const appsShowOperation = (message, state = "running") => {
  const dialog = appsEl("operation");
  if (!dialog.open && state !== "running") return;
  dialog.dataset.state = state;
  appsEl("operation-title").textContent = message;
  appsEl("operation-status").className = state === "running" ? "app-operation-status" : `app-operation-status ${state}`;
  appsEl("operation-spinner").hidden = state !== "running";
  appsEl("operation-note").textContent = state === "running" ? "Please wait. This can take a moment." : "";
  appsEl("operation-note").hidden = state !== "running";
  appsEl("operation-close").hidden = state === "running";
  if (!dialog.open) {
    appsEl("operation-details").open = false;
    dialog.showModal();
  }
};
const appsDetails = (status, receipt = null) => {
  const details = receipt ? JSON.stringify(receipt, null, 2) : "";
  for (const prefix of ["", "operation-"]) {
    appsEl(`${prefix}execution`).textContent = status;
    appsEl(`${prefix}result`).textContent = details;
  }
};
const appsError = (message, target = "error") => {
  if (message) appsErrors.set(target, String(message));
  else appsErrors.delete(target);
  const element = appsEl(target);
  if (!element) return;
  element.textContent = String(message);
  element.hidden = !message;
};
const appsErrorTarget = (operation, name) => operation === "upload" ? "upload-error"
  : operation === "remove" ? `remove-error-${name}`
  : operation.startsWith("display") ? "frontend-error"
  : ["verify", "install", "update", "discard"].includes(operation) ? "package-error" : "error";
const appsFailure = (error, target, context = "") => {
  appsInfo("");
  const message = context ? `${context}: ${error.message}` : error.message;
  appsError(message, [401, 403].includes(error.status) ? "error" : target);
  appsShowOperation(message, "error");
};
const appsInfo = (message) => { appsEl("message").textContent = message; };
const appsClearMessages = (keepOperation = false) => {
  for (const target of appsErrors.keys()) appsError("", target);
  for (const target of ["installed-success", "package-success"]) {
    appsEl(target).hidden = true;
    appsEl(target).textContent = "";
  }
  appsInfo("");
  appsDetails("");
  if (!keepOperation) appsCloseOperation();
};
const appsContext = (operation, name) => name ? `${operation} app "${name}"` : operation;
const appsProgress = (operation, name) => `${({install: "Installing", update: "Updating", remove: "Removing"})[operation] || operation}${name ? ` ${name}` : ""}…`;
const appsCompletionError = (execution, name) => {
  const app = appsState.installed.find((item) => item.name === name);
  if (execution.operation === "remove") return app
    ? `Package Core reported success, but app "${name}" is still installed. Removal could not be confirmed.` : "";
  const expected = execution.result && execution.result.package;
  return !expected || !app || ["name", "version", "release_serial"].some((field) => app[field] !== expected[field])
    ? `Package Core reported success, but the installed state of app "${name}" does not match the package result.` : "";
};
const appsButton = (label, action, disabled = false) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary-button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", action);
  return button;
};
const appsPost = (path, payload) => requestJson(appsRoot + path, {
  method: "POST",
  headers: {"Content-Type": "application/json", "X-Fre3nder-CSRF": csrfToken},
  body: JSON.stringify(payload),
});
const appsFormat = (size) => size == null ? "unavailable" : `${(size / (1024 * 1024)).toFixed(1)} MiB`;

const appsRenderInstalled = () => {
  const list = appsEl("installed");
  list.replaceChildren();
  const repository = appsState.repository;
  const availability = repository?.availability;
  const updates = ["checked", "cached"].includes(availability) && Array.isArray(repository.updates)
    ? repository.updates : [];
  let repositoryStatus = "Repository update information unavailable. Update availability is unknown.";
  if (availability === "checked") repositoryStatus = updates.length
    ? "Repository check succeeded. Update offers are listed below." : "Repository check succeeded. No updates offered.";
  else if (availability === "cached") repositoryStatus = "Repository check failed. Showing cached information.";
  else if (repository?.configuration === "unconfigured") repositoryStatus = "Repository not configured. Update availability is unknown.";
  else if (repository?.check === "error") repositoryStatus = "Repository check failed. Update availability is unknown.";
  const repositoryDetails = [repositoryStatus];
  if (repository?.identity?.name) repositoryDetails.push(repository.identity.name);
  if (repository?.revision != null) repositoryDetails.push(`Index revision: ${repository.revision}`);
  if (repository?.last_success) repositoryDetails.push(`Last successful check: ${repository.last_success}`);
  if (repository?.error?.message) repositoryDetails.push(repository.error.message);
  appsEl("repository").textContent = repositoryDetails.join(" · ");
  for (const app of appsState.installed) {
    const card = document.createElement("section");
    card.className = "app-entry";
    const title = document.createElement("h3");
    title.textContent = `${app.name} · ${app.version}`;
    card.append(title);
    const update = updates.find((item) => item.name === app.name);
    if (update?.offered) {
      const offer = document.createElement("p");
      offer.className = "section-note";
      offer.textContent = `Update: ${update.offered.version} (${update.offered.channel})${availability === "cached" ? " · Cached information" : ""}`;
      card.append(offer);
    }
    const description = document.createElement("p");
    description.className = "section-note";
    const caps = [app.web_frontend ? "Web" : null, app.display_frontend ? "Display" : null].filter(Boolean);
    description.textContent = `${app.publisher} · ${app.system_app ? "System app · Protected" : "Installed"} · Storage: ${(app.storage || "sys").toUpperCase()} · ${caps.join(" / ") || "Service"}`;
    card.append(description);
    const selection = document.createElement("p");
    selection.className = "section-note";
    selection.textContent = [appsState.web.active === app.name ? "Active web frontend" : "",
      appsState.display.active === app.name ? "Selected display frontend" : ""].filter(Boolean).join(" · ");
    if (selection.textContent) card.append(selection);
    const state = document.createElement("p");
    state.className = "section-note";
    state.textContent = "Service status: not checked";
    card.append(state);
    const actions = document.createElement("div");
    actions.className = "app-actions";
    actions.append(
      appsButton("Details / status", async () => {
        try {
          const answer = await requestJson(`${appsRoot}detail?name=${encodeURIComponent(app.name)}`);
          const runtime = answer.app.running ? "Healthy / active according to service" : "Not healthy / not running according to service";
          state.textContent = `Service status: ${runtime}`;
          appsInfo(`${app.name}: release serial ${answer.app.release_serial}, fingerprint ${answer.app.fingerprint || "unknown"}`);
        } catch (error) { state.textContent = `Service status unavailable: ${error.message}`; }
      }),
      appsButton("Update", () => {
        appsSelectedUpdate = app.name;
        appsVerified = null;
        appsEl("file").value = "";
        appsClearMessages();
        appsInfo(`Updating ${app.name}: choose its new signed .fre3app package below.`);
        appsRenderVerified();
        appsEl("file").focus();
      }, appsBusy),
      ...(app.system_app ? [] : [appsButton("Remove", () => appsRemove(app), appsBusy)]),
    );
    card.append(actions);
    const error = document.createElement("p");
    error.id = `apps-remove-error-${app.name}`;
    error.className = "error";
    error.setAttribute("role", "alert");
    error.hidden = true;
    card.append(error);
    list.append(card);
  }
  if (!appsState.installed.length) list.textContent = "No apps installed.";
};

const appsRenderSelection = () => {
  const list = appsEl("display-list");
  list.replaceChildren();
  const active = appsState.display.active;
  appsEl("web-active").textContent = appsState.web.active || "None selected (port 80 may have no frontend)";
  appsEl("display-active").textContent = active || "Disabled";
  for (const app of appsState.display.apps) {
    const selected = app.name === active;
    const unknown = selected && typeof app.running !== "boolean";
    const row = document.createElement("div");
    row.className = "app-actions";
    const name = document.createElement("span");
    name.textContent = `${app.name}${selected ? " (selected)" : ""}`;
    const label = !selected ? "Select" : app.running === true ? "Selected" : unknown ? "Check status" : "Retry start";
    row.append(name, appsButton(label, () => {
      if (unknown) {
        appsClearMessages();
        return appsLoad().catch((error) => appsError(error.message, "frontend-error"));
      }
      return appsAction("display/select", {name: app.name});
    }, appsBusy || (selected && app.running === true)));
    list.append(row);
  }
  appsEl("display-disable").disabled = appsBusy || !active;
};

const appsRenderStaging = () => {
  const select = appsEl("staged");
  const old = select.value;
  select.replaceChildren();
  for (const item of appsState.packages) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.id} · ${appsFormat(item.size)}`;
    select.append(option);
  }
  if (appsState.packages.some((p) => p.id === old)) select.value = old;
  select.disabled = appsBusy || !appsState.packages.length;
  appsEl("verify").disabled = select.disabled;
  appsEl("discard").disabled = select.disabled;
};

const appsRenderVerified = () => {
  const details = appsEl("verified");
  details.replaceChildren();
  appsEl("cancel-update").hidden = !appsSelectedUpdate;
  appsEl("cancel-update").disabled = appsBusy;
  appsEl("install-options").hidden = true;
  const allowed = Boolean(appsVerified && appsState.packages.some((item) => item.id === appsVerified.id)
    && appsState.verified_packages.includes(appsVerified.id));
  if (allowed) {
    const item = appsVerified.package;
    const existing = appsState.installed.find((app) => app.name === item.name);
    if (appsSelectedUpdate && (item.name !== appsSelectedUpdate || !existing)) {
      const error = document.createElement("p");
      error.className = "error";
      error.textContent = item.name !== appsSelectedUpdate
        ? `Update selected for ${appsSelectedUpdate}, but this package belongs to ${item.name}. Choose a matching package or cancel the selected update.`
        : `The selected app ${appsSelectedUpdate} is no longer installed. Cancel the selected update to start a general upload.`;
      details.append(error);
      return;
    }
    const content = document.createElement("p");
    content.textContent = `${item.name} ${item.version} · Publisher ${item.publisher} · Signature verified / publisher trusted · Web: ${item.web_frontend ? "yes" : "no"} · Display: ${item.display_frontend ? "yes" : "no"}`;
    details.append(content);
    if (existing) {
      const warning = document.createElement("p");
      warning.className = "section-note";
      warning.textContent = `Installed version: ${existing.version}. Storage: ${(existing.storage || "sys").toUpperCase()} (preserved). Update preserves existing selections. Downgrades are not enabled.`;
      details.append(warning);
    } else {
      appsEl("install-options").hidden = false;
      const select = appsEl("install-storage");
      const chosen = select.value === "home" ? "home" : "sys";
      select.replaceChildren();
      for (const [role, label] of [["sys", "SYS – System storage (default)"], ["home", "HOME – Persistent storage"]]) {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = `${label} · Free: ${appsFormat(appsState.storage[role]?.available_bytes)}`;
        select.append(option);
      }
      select.value = chosen;
      select.disabled = appsBusy;
    }
    details.append(appsButton(existing ? "Confirm update" : "Confirm installation", async () => {
      if (!csrfToken || appsBusy || (appsSelectedUpdate && item.name !== appsSelectedUpdate)) return;
      const storage = existing ? existing.storage || "sys" : appsEl("install-storage").value;
      if (!window.confirm(`${existing ? "Update" : "Install"} ${item.name} to ${item.version} (${item.publisher})? Storage: ${storage.toUpperCase()}${existing ? " (preserved)" : ""}.`)) {
        appsCancelUpdate();
        return;
      }
      await appsAction(existing ? "update" : "install", existing
        ? {package_id: appsVerified.id, name: existing.name} : {package_id: appsVerified.id, storage});
    }, appsBusy));
  } else {
    details.textContent = "Upload and verify a signed package before selecting Install or Update.";
  }
};

const appsCancelUpdate = () => {
  appsSelectedUpdate = null;
  appsVerified = null;
  appsEl("file").value = "";
  appsClearMessages();
  appsInfo("Choose a signed .fre3app package for installation or update.");
  appsRenderVerified();
};

const appsRender = () => {
  if (!appsState) return;
  const execution = appsState.execution;
  appsBusy = appsSubmitting || Boolean(execution && ["uploading", "running", "unknown"].includes(execution.state));
  appsRenderInstalled();
  appsRenderSelection();
  appsRenderStaging();
  if (execution && !appsSubmitting) {
    const name = execution.name || execution.result?.package?.name;
    if (["uploading", "running"].includes(execution.state)) {
      appsDetails(`${appsContext(execution.operation, name)}: ${execution.state}`, execution);
      appsInfo(appsProgress(execution.operation, name));
      appsShowOperation(appsProgress(execution.operation, name));
    }
    if (["succeeded", "failed", "unknown"].includes(execution.state) && execution.id !== appsCompletedExecution) {
      appsClearMessages(true);
      let state = execution.state;
      if (execution.state === "succeeded" && execution.operation === "verify" && execution.result && execution.result.package) {
        appsVerified = {id: execution.package_id, package: execution.result.package};
        appsEl("install-storage").value = "sys";
      }
      if (execution.state === "succeeded" && ["install", "update", "remove"].includes(execution.operation)) {
        const failure = appsCompletionError(execution, name);
        if (failure) {
          state = "unconfirmed";
          appsFailure({message: failure}, appsErrorTarget(execution.operation, name));
        } else {
          appsVerified = null;
          appsSelectedUpdate = null;
          const message = appsEl(execution.operation === "remove" ? "installed-success" : "package-success");
          message.textContent = `App "${name}" was ${{install: "installed", update: "updated", remove: "removed"}[execution.operation]} successfully.`;
          message.hidden = false;
          appsShowOperation(message.textContent, "success");
        }
      } else if (execution.state === "succeeded") {
        appsShowOperation(`${appsContext(execution.operation, name)} completed successfully.`, "success");
      }
      if (execution.state === "failed" || execution.state === "unknown") {
        appsFailure({message: execution.error ? execution.error.message : "Application operation failed."},
          appsErrorTarget(execution.operation, name), appsContext(execution.operation, name));
      }
      appsDetails(`${appsContext(execution.operation, name)}: ${state}`, execution.result || execution.error || {});
      appsCompletedExecution = execution.id;
    }
  } else if (!execution && !appsSubmitting && !appsEl("operation").open) {
    appsDetails("No recent operation");
  }
  appsRenderVerified();
  for (const [target, message] of appsErrors) appsError(message, target);
  appsEl("upload").disabled = appsBusy || !csrfToken;
  appsEl("acknowledge").hidden = !(execution && execution.state === "unknown");
  appsEl("storage").textContent = `Available HOME upload space: ${appsFormat(appsState.storage.available_bytes)}. Maximum upload: ${appsFormat(appsState.storage.max_package_bytes)}. Uninstalled uploads are discarded at printer reboot.`;
};

const appsLoad = async () => {
  if (!csrfToken) return;
  try {
    const reply = await requestJson(appsRoot + "status");
    appsState = reply.apps;
    appsRender();
    const state = appsState;
    const selected = state.display.apps.find((app) => app.name === state.display.active);
    if (selected && !appsBusy && typeof selected.running !== "boolean") {
      try {
        const detail = await requestJson(`${appsRoot}detail?name=${encodeURIComponent(selected.name)}`);
        selected.running = detail.app.running;
      } catch (error) {
        if (appsState === state && csrfToken) appsError(`Could not check display "${selected.name}": ${error.message}`, "frontend-error");
      }
      if (appsState === state && csrfToken) appsRenderSelection();
    }
  } finally {
    if (appsPoll) clearTimeout(appsPoll);
    appsPoll = null;
    if (csrfToken && appsBusy && appsState?.execution?.state !== "unknown") {
      appsPoll = setTimeout(() => appsLoad().catch((error) => appsError(error.message)), 1300);
    }
  }
};

const appsAction = async (operation, payload) => {
  if (!csrfToken || (appsBusy && (operation !== "acknowledge" || appsState?.execution?.state !== "unknown"))) return;
  const name = payload.name || (appsVerified && appsVerified.id === payload.package_id ? appsVerified.package.name : null);
  const target = appsErrorTarget(operation, name);
  appsClearMessages();
  appsInfo(appsProgress(operation, name));
  appsSubmitting = true;
  appsRender();
  appsShowOperation(appsProgress(operation, name));
  try {
    const reply = await appsPost(operation, payload);
    if (operation === "discard") appsCancelUpdate();
    if (reply.execution) appsBusy = true;
    else appsCloseOperation();
  } catch (error) {
    appsDetails(`${appsContext(operation, name)}: request failed`, {message: error.message, code: error.code, status: error.status});
    appsFailure({message: `${error.message} No automatic retry was performed.`, status: error.status}, target,
      appsContext(operation, name));
  } finally {
    appsSubmitting = false;
    await appsLoad().catch((error) => appsError(error.message));
  }
};

const appsRemove = (app) => {
  const effects = [];
  if (appsState.web.active === app.name) effects.push("The port-80 web frontend will disappear.");
  if (appsState.display.active === app.name) effects.push("The local display may be left without an active UI.");
  if (!window.confirm(`Remove ${app.name} (${app.version})?\n${effects.join("\n") || "Its service will be uninstalled according to Package Core policy."}`)) return;
  return appsAction("remove", {name: app.name});
};

appsEl("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!csrfToken || appsBusy) return;
  appsClearMessages();
  const file = appsEl("file").files[0];
  if (!file || !file.name.endsWith(".fre3app") || file.size < 1 || file.size > 256 * 1024 * 1024) {
    appsError("Choose a .fre3app file between 1 byte and 256 MiB.", "upload-error"); return;
  }
  appsVerified = null;
  appsSubmitting = true;
  appsRender();
  appsInfo(`Uploading ${file.name}…`);
  appsShowOperation(`Uploading ${file.name}…`);
  const progress = appsEl("progress");
  progress.hidden = false;
  progress.value = 0;
  try {
    await new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", appsRoot + "upload");
      request.responseType = "json";
      request.setRequestHeader("Content-Type", "application/octet-stream");
      request.setRequestHeader("X-Fre3nder-CSRF", csrfToken);
      request.setRequestHeader("X-Fre3nder-Filename", encodeURIComponent(file.name));
      request.upload.onprogress = (value) => {
        if (value.lengthComputable) progress.value = value.loaded * 100 / value.total;
      };
      request.onload = () => {
        const response = request.response;
        if (request.status === 202 && response && response.ok && response.api_version === 1) resolve(response.execution);
        else {
          const error = new Error(response && response.error ? response.error.message : "Upload rejected");
          error.status = request.status;
          reject(error);
        }
      };
      request.onerror = request.onabort = () => reject(new Error("Upload connection lost; inspect server state before retrying"));
      request.send(file);
    });
    appsInfo("Upload accepted. Signature and package verification running…");
  } catch (error) { appsFailure(error, "upload-error"); }
  finally {
    progress.hidden = true;
    appsSubmitting = false;
    await appsLoad().catch((error) => appsError(error.message));
  }
});
appsEl("cancel-update").addEventListener("click", () => {
  if (!appsBusy) appsCancelUpdate();
});
appsEl("verify").addEventListener("click", () => {
  appsVerified = null;
  appsAction("verify", {package_id: appsEl("staged").value});
});
appsEl("discard").addEventListener("click", async () => {
  if (!window.confirm("Discard this staged upload without installing it?")) return;
  await appsAction("discard", {package_id: appsEl("staged").value});
});
appsEl("display-disable").addEventListener("click", () => {
  if (window.confirm("Disable the selected display frontend? The local screen may be left without a UI."))
    appsAction("display/disable", {});
});
appsEl("acknowledge").addEventListener("click", async () => {
  if (window.confirm("Have you inspected the actual installed app state? This only acknowledges an unknown result; it does not undo or repeat the operation."))
    await appsAction("acknowledge", {});
});
appsEl("operation-close").addEventListener("click", appsCloseOperation);
appsEl("operation").addEventListener("cancel", (event) => {
  if (appsEl("operation").dataset.state === "running") event.preventDefault();
});
window.addEventListener("pagehide", () => { if (appsPoll) clearTimeout(appsPoll); appsPoll = null; });
