"use strict";

let csrfToken = null;

const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

const setStatus = (id, value, kind) => {
  const element = document.getElementById(id);
  element.textContent = value;
  element.className = `status status-${kind}`;
};

const requestJson = async (path, options = {}) => {
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
    headers: {
      "Accept": "application/json",
      ...(options.headers || {}),
    },
  });

  let data;
  try {
    data = await response.json();
  } catch (_error) {
    const error = new Error("Management API returned an invalid response.");
    error.status = response.status;
    error.accepted = response.status === 202;
    throw error;
  }

  if (!response.ok || data.ok !== true || data.api_version !== 1) {
    const apiError = data && data.error;
    const message =
      apiError && typeof apiError.message === "string"
        ? apiError.message
        : "Management API request failed.";
    const error = new Error(message);
    error.code = apiError && apiError.code;
    error.status = response.status;
    error.rejected = data.api_version === 1 && Boolean(apiError && apiError.message);
    throw error;
  }

  return data;
};

const renderAuth = (auth) => {
  const authenticated =
    auth &&
    auth.authenticated === true &&
    typeof auth.csrf_token === "string" &&
    auth.csrf_token.length > 0;
  csrfToken = authenticated ? auth.csrf_token : null;
  const label = authenticated ? "Unlocked" : "Locked";
  const kind = authenticated ? "ok" : "neutral";

  setStatus("admin-status", label, kind);
  setStatus("admin-status-sidebar", label, kind);

  const action = document.getElementById("admin-action");
  action.disabled = false;
  action.textContent = authenticated ? "Lock" : "Unlock";
  action.dataset.authenticated = authenticated ? "true" : "false";

  document.getElementById("unlock-form").hidden = true;
  document.getElementById("auth-error").hidden = true;
  document.getElementById("admin-note").textContent = authenticated
    ? "This browser has temporary administrative access."
    : "Administrative actions require a temporary paired browser session.";
  if (authenticated) {
    loadOta().catch(handleStatusError);
    if (typeof appsLoad === "function") appsLoad().catch((error) => appsError(error.message));
  } else {
    stopOtaPolling();
    disableOtaControls();
    if (typeof appsPoll !== "undefined") {
      if (appsPoll) clearTimeout(appsPoll);
      appsPoll = null;
      appsState = null;
      appsVerified = null;
      appsSelectedUpdate = null;
      appsCompletedExecution = null;
      appsSubmitting = false;
      appsBusy = false;
      appsClearMessages();
      document.getElementById("apps-cancel-update").hidden = true;
      document.getElementById("apps-install-options").hidden = true;
      document.getElementById("apps-verified").replaceChildren();
      document.getElementById("apps-installed").replaceChildren();
    }
  }
};

const loadOverview = async () => {
  const [systemResponse, maintenanceResponse, authResponse] = await Promise.all([
    requestJson("/fre3nder/api/v1/system"),
    requestJson("/fre3nder/api/v1/maintenance"),
    requestJson("/fre3nder/api/v1/auth/session"),
  ]);

  const system = systemResponse.system;
  const maintenance = maintenanceResponse.maintenance;

  setText("system-version", system.version);
  setStatus(
    "root-status",
    system.root_status,
    system.root_status === "active" ? "ok" : "neutral",
  );
  setStatus(
    "maintenance-status",
    maintenance.enabled ? "enabled" : "disabled",
    maintenance.enabled ? "on" : "neutral",
  );
  setStatus(
    "web-status",
    maintenance.web_status,
    maintenance.web_status === "active" ? "ok" : "neutral",
  );
  renderAuth(authResponse.auth);
};

const showAuthError = (message) => {
  const error = document.getElementById("auth-error");
  error.textContent = message;
  error.hidden = false;
};

document.getElementById("admin-action").addEventListener("click", async (event) => {
  const action = event.currentTarget;
  if (action.dataset.authenticated !== "true") {
    document.getElementById("unlock-form").hidden = false;
    document.getElementById("pairing-code").focus();
    return;
  }

  action.disabled = true;
  try {
    const response = await requestJson("/fre3nder/api/v1/auth/lock", {
      method: "POST",
      headers: { "X-Fre3nder-CSRF": csrfToken },
    });
    renderAuth(response.auth);
  } catch (error) {
    action.disabled = false;
    showAuthError(error.message);
  }
});

document.getElementById("unlock-cancel").addEventListener("click", () => {
  document.getElementById("unlock-form").hidden = true;
  document.getElementById("auth-error").hidden = true;
});

document.getElementById("unlock-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const input = document.getElementById("pairing-code");
  const code = input.value.replace(/\s/g, "");
  if (!/^\d{6}$/.test(code)) {
    showAuthError("Enter the six-digit pairing code.");
    return;
  }

  const action = document.getElementById("admin-action");
  action.disabled = true;
  document.getElementById("auth-error").hidden = true;

  try {
    const response = await requestJson("/fre3nder/api/v1/auth/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    input.value = "";
    renderAuth(response.auth);
  } catch (error) {
    action.disabled = false;
    showAuthError(error.message);
  }
});

let otaState = null;
let otaActivity = null;
let otaFailure = null;
let otaPreflight = null;
let verifiedPackageId = null;
let localFileChanged = false;
let otaPollTimer = null;
let otaEpoch = 0;
let otaStatusRead = 0;
const otaElement = (name) => document.getElementById(`ota-${name}`);
const formatBytes = (bytes) => `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
const receiptKey = "fre3nder-ota-receipt";

// Correlation and the reboot request outcome survive reload. Core owns installation phases.
const readOtaReceipt = () => {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(receiptKey));
    return value && /^[0-9a-f]{32}$/.test(value.package_id) ? value : null;
  } catch (_error) { return null; }
};
let otaReceipt = readOtaReceipt();
// An interrupted request cannot be confirmed by reloading or repeating it.
if (otaReceipt && (otaReceipt.reboot_status === "pending" || otaReceipt.reboot_requested)) {
  otaReceipt.reboot_status = "unclear";
}
const saveOtaReceipt = (receipt) => {
  otaReceipt = receipt;
  try {
    if (receipt) window.sessionStorage.setItem(receiptKey, JSON.stringify(receipt));
    else window.sessionStorage.removeItem(receiptKey);
  } catch (_error) { /* In-memory correlation still works while this page is open. */ }
};
const transactionPackageId = (transaction) => transaction && transaction.package.path.split("/").pop().replace(/\.ota$/, "");
const rememberTransaction = (transaction) => {
  const packageId = transactionPackageId(transaction);
  if (!transaction || !/^[0-9a-f]{32}$/.test(packageId)
      || (otaReceipt && otaReceipt.package_id !== packageId)) return;
  saveOtaReceipt({
    ...otaReceipt, package_id: packageId, transaction_id: transaction.transaction_id,
    version: transaction.package.version, sha256: transaction.package.sha256,
    size: transaction.package.size, slot: transaction.target.slot,
    home: transaction.backup_selection.home.selected ? "usb" : "none",
    sys: transaction.backup_selection.sys.selected ? transaction.backup_selection.sys.target : "none",
  });
};
const rebootStatus = () => otaReceipt && otaReceipt.reboot_status;
const renderReboot = () => {
  const status = rebootStatus();
  otaElement("workflow").hidden = Boolean(status);
  otaElement("reboot-view").hidden = !status;
  if (!status) return;
  disableOtaControls();
  stopOtaPolling();
  renderNavigation();
  setText("ota-reboot-status", status === "requested" ? "Printer restart requested"
    : status === "pending" ? "Sending printer restart request" : "Printer restart status unclear");
  setText("ota-reboot-message", status === "requested"
    ? "The update was written and verified. The printer has been instructed to restart into the updated system."
    : status === "pending"
      ? "The update was written and verified. The restart request is being sent; its acceptance has not yet been confirmed."
      : "The update was written and verified. The connection or request result was lost before restart acceptance could be confirmed. Please inspect the printer to check whether it restarted.");
};
const sameVersionNotice = (context) => {
  if (!context || context.runtime.installed_version !== context.package.version) return "";
  const packageId = context.package_id || (context.package.path && transactionPackageId(context));
  const metadata = context.package.artifact_mode ? context.package
    : otaPreflight && otaPreflight.package_id === packageId ? otaPreflight.package : null;
  return metadata && metadata.artifact_mode === "development"
    ? "Development build: The version numbers match, but the builds may differ. The selected package will be installed."
    : "The version numbers match. The selected package will be installed again; matching version numbers do not establish identical builds.";
};
const operationStep = {
  "backup-plan": "prepare", backup: "backups", confirm: "write", write: "write",
  readback: "readback", "prepare-activation": "activate",
};
const operationLabel = {
  upload: "Uploading package", verify: "Verifying package", preflight: "Checking compatibility",
  "backup-plan": "Preparing update", backup: "Creating and verifying backups",
  confirm: "Preparing system write", write: "Writing system", readback: "Verifying installation",
  "prepare-activation": "Preparing restart", reboot: "Requesting printer restart",
};
const nextOperation = {
  "awaiting-confirmation": "confirm", confirmed: "write",
  "written-awaiting-readback": "readback", "readback-verified": "prepare-activation",
  "activation-prepared": "reboot",
};
const disableOtaControls = () => {
  for (const name of ["upload", "file", "package", "home", "sys", "check", "update"]) otaElement(name).disabled = true;
};
const stopOtaPolling = () => { clearTimeout(otaPollTimer); otaPollTimer = null; };
const showOtaError = (error) => {
  otaFailure = { message: error.message, operation: error.operation || (otaActivity && otaActivity.operation) };
  setText("ota-error", error.message);
  otaElement("error").hidden = false;
  if (["verify", "preflight"].includes(otaFailure.operation)) otaElement("staged").open = true;
  if (error.status === 401) renderAuth({ authenticated: false });
};
const setOptions = (select, values, selected) => {
  const existing = Array.from(select.children);
  if (existing.length !== values.length || existing.some((option, index) =>
    option.value !== values[index][0] || option.textContent !== values[index][1])) {
    select.replaceChildren();
    for (const [value, label] of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
  }
  if (values.some(([value]) => value === selected)) select.value = selected;
};
const progressStatus = (id, completed, active, failed) => {
  setStatus(id, completed ? "Done" : failed ? "Failed" : active ? "In progress" : "Waiting",
    completed ? "ok" : active ? "on" : "neutral");
};
const currentChoices = () => ({ home: otaElement("home").value, sys: otaElement("sys").value });
const canUpdate = () => {
  if (!csrfToken || !otaState || otaActivity || localFileChanged || otaState.core.busy || rebootStatus()) return false;
  const { core, execution } = otaState;
  if (execution && ["running", "uploading", "unknown"].includes(execution.state)) return false;
  const transaction = core.transaction;
  if (transaction) {
    return Boolean(otaReceipt && otaReceipt.transaction_id === transaction.transaction_id
      && nextOperation[transaction.state]
      && (otaElement("package").value || transaction.state === "activation-prepared"));
  }
  const choices = currentChoices();
  return Boolean(!core.activation && otaPreflight && otaPreflight.package_id === otaElement("package").value
    && choices.home && choices.sys);
};

const renderOta = () => {
  disableOtaControls();
  renderReboot();
  if (rebootStatus()) return;
  if (!otaState) return;
  const { core, execution, packages, storage } = otaState;
  const transaction = core.transaction;
  const selected = (otaReceipt && otaReceipt.package_id) || transactionPackageId(transaction)
    || otaElement("package").value || (execution && execution.package_id);
  setOptions(otaElement("package"), packages.map((item) => [item.id, `${item.id} (${formatBytes(item.size)})`]), selected);
  if (transaction && !packages.some((item) => item.id === transactionPackageId(transaction))) {
    setOptions(otaElement("package"), [["", "Transaction package unavailable"]]);
  }
  const packageId = otaElement("package").value;
  const relevant = execution && (execution.package_id === packageId
    || (transaction && execution.transaction_id === transaction.transaction_id));
  const result = relevant && execution.state === "succeeded"
    && (!otaActivity || execution.id === otaActivity.execution_id) && execution.result;
  if (result && ["preflight", "backup-plan"].includes(result.operation)) {
    otaPreflight = { package_id: packageId, ...result };
    verifiedPackageId = packageId;
  } else if (result && result.operation === "verify") verifiedPackageId = packageId;
  if (relevant && execution.state === "failed" && ["verify", "preflight"].includes(execution.operation)) {
    otaPreflight = null;
    if (execution.operation === "verify") verifiedPackageId = null;
  }
  const preflight = otaPreflight && otaPreflight.package_id === packageId ? otaPreflight : null;
  const activation = core.activation;
  const handoff = activation && otaReceipt && activation.transaction_id === otaReceipt.transaction_id
    && activation.package.sha256 === otaReceipt.sha256 && activation.package.size === otaReceipt.size
    && activation.package.version === otaReceipt.version && activation.target.slot === otaReceipt.slot ? activation : null;
  const context = transaction || preflight || (handoff && {
    package: handoff.package, runtime: handoff.previous_runtime, target: handoff.target,
  });
  const unknown = execution && execution.state === "unknown";
  const busy = otaActivity || core.busy || (execution && ["uploading", "running"].includes(execution.state));
  const activeOperation = (otaActivity && otaActivity.operation) || (relevant && execution.state === "running" && execution.operation);
  const failure = otaFailure || (!otaActivity && relevant && ["failed", "unknown"].includes(execution.state)
    && { ...execution.error, operation: execution.operation });
  otaElement("error").hidden = !failure;
  if (failure) setText("ota-error", failure.message);
  setText("ota-phase", unknown ? "Execution outcome unknown. Inspect the printer through SSH before proceeding."
    : failure ? (transaction || operationStep[failure.operation]
      ? "Update paused. Review the error before explicitly continuing."
      : "Package check failed. Review the error and retry the check before updating.")
    : activeOperation ? `${operationLabel[activeOperation]}…`
    : busy ? "Waiting for the active OTA operation. No operation will be repeated."
    : transaction ? "Update paused. Confirm continuation from the recorded Core state."
    : localFileChanged ? "Upload and verify the selected local file before starting the update."
    : preflight ? "Package ready. Choose both backup options, then confirm the update."
    : "Upload a package or check a staged package.");
  setText("ota-storage", `${formatBytes(storage.available_bytes)} free in SYS. Upload limit: 96 MiB.`);
  progressStatus("ota-package-upload", Boolean(packageId) && activeOperation !== "upload", activeOperation === "upload", failure && failure.operation === "upload");
  progressStatus("ota-package-verify", Boolean(context || (packageId && verifiedPackageId === packageId)), activeOperation === "verify", failure && failure.operation === "verify");
  progressStatus("ota-package-preflight", Boolean(context), activeOperation === "preflight", failure && failure.operation === "preflight");

  otaElement("details").replaceChildren();
  if (context) {
    for (const [label, value] of [
      ["Installed version", context.runtime.installed_version], ["Target version", context.package.version],
      ["Active slot", context.runtime.active_slot], ["Inactive target", context.target.slot],
      ["HOME", "Preserved"], ["SYS", "Reset when the updated system boots"],
    ]) {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label; dd.textContent = value; row.append(dt, dd); otaElement("details").append(row);
    }
  }
  const notice = sameVersionNotice(context);
  otaElement("reinstall").hidden = !notice;
  setText("ota-reinstall", notice);
  const offer = preflight && preflight.backup_offer;
  for (const role of ["home", "sys"]) {
    const previous = otaElement(role).value;
    const values = [["", "Choose explicitly…"]];
    if (transaction || handoff) {
      const choice = transaction && transaction.backup_selection[role];
      const target = choice ? (choice.selected ? choice.target : "none") : otaReceipt[role];
      values.push([target, target === "none" ? "No backup" : target.toUpperCase()]);
      setOptions(otaElement(role), values, target);
    } else {
      if (offer && offer[role].offered) for (const target of offer[role].targets) values.push([target, target.toUpperCase()]);
      if (offer && offer[role].required === false) values.push(["none", "No backup"]);
      setOptions(otaElement(role), values, previous || (otaReceipt && otaReceipt[role]));
    }
  }
  const choices = currentChoices();
  const skipped = choices.home === "none" && choices.sys === "none";
  setText("ota-backup-label", skipped ? "Backups skipped" : "Creating backups");
  const phase = transaction ? Object.keys(nextOperation).indexOf(transaction.state)
    : handoff ? (handoff.state === "activation-prepared" ? 4 : 3) : -1;
  const done = {
    prepare: Boolean(transaction || handoff || (preflight && preflight.operation === "backup-plan")),
    backups: Boolean(transaction || handoff), write: phase >= 2, readback: phase >= 3,
    activate: phase >= 4,
  };
  for (const step of Object.keys(done)) {
    progressStatus(`ota-progress-${step}`, done[step], operationStep[activeOperation] === step,
      failure && operationStep[failure.operation] === step);
  }
  if (skipped && done.backups) setStatus("ota-progress-backups", "Skipped", "ok");
  setText("ota-transaction", transaction ? `Transaction: ${transaction.transaction_id}`
    : otaReceipt && otaReceipt.transaction_id ? `Expected transaction: ${otaReceipt.transaction_id}` : "No transaction created.");
  otaElement("backups").replaceChildren();
  if (transaction) for (const role of ["home", "sys"]) {
    const backup = transaction.backup_result[role];
    const line = document.createElement("p");
    line.textContent = backup.selected ? `${role.toUpperCase()}: ${backup.archive}; ${formatBytes(backup.size)}; ${backup.verified === true ? "verified at creation" : "verification required before writing"}; SHA-256 ${backup.sha256}` : `${role.toUpperCase()}: explicitly declined`;
    otaElement("backups").append(line);
  }
  setText("ota-known-good", core.known_good ? `Last validated boot: ${core.known_good.version}, slot ${core.known_good.slot}; transaction ${core.known_good.transaction_id}.` : "No validated update boot is recorded.");
  if (!csrfToken || busy || unknown) return;
  const locked = Boolean(transaction || core.activation);
  otaElement("upload").disabled = locked;
  otaElement("file").disabled = locked;
  otaElement("package").disabled = locked;
  otaElement("check").disabled = locked || !packageId;
  otaElement("check").textContent = (otaFailure && otaFailure.operation === "preflight")
    || (relevant && execution.state === "failed" && execution.operation === "preflight") ? "Retry compatibility check" : "Check package";
  for (const role of ["home", "sys"]) otaElement(role).disabled = locked || !offer;
  otaElement("update").textContent = transaction ? "Continue update" : "Update Fre3nder";
  otaElement("update").disabled = !canUpdate();
};

const handleStatusError = (error) => {
  disableOtaControls();
  if (rebootStatus()) renderReboot();
  else showOtaError(error);
};
const scheduleOtaPoll = () => {
  stopOtaPolling();
  if (csrfToken && !otaActivity && !rebootStatus()) otaPollTimer = setTimeout(async () => {
    try { await loadOta(); } catch (error) { handleStatusError(error); }
    scheduleOtaPoll();
  }, 2000);
};
const loadOta = async () => {
  if (!csrfToken || (rebootStatus() && !(rebootStatus() === "pending" && otaActivity && otaActivity.operation === "reboot"))) return null;
  const read = ++otaStatusRead;
  const response = await requestJson("/fre3nder/api/v1/ota/status");
  if (read === otaStatusRead) {
    otaState = response.ota;
    rememberTransaction(otaState.core.transaction);
    renderOta();
    scheduleOtaPoll();
  }
  return response.ota;
};
const assertActivity = (epoch) => {
  if (!otaActivity || epoch !== otaEpoch || !csrfToken) throw new Error("Update interrupted. Unlock and explicitly confirm continuation; no operation was repeated.");
};
const waitExecution = async (execution, epoch) => {
  while (true) {
    assertActivity(epoch);
    const state = await loadOta();
    assertActivity(epoch);
    const observed = state.execution;
    if (!observed || observed.id !== execution.id) throw new Error("Execution status changed or was lost. Inspect the actual Core state before continuing.");
    if (observed.state === "succeeded") return observed.result;
    if (["failed", "unknown"].includes(observed.state)) throw Object.assign(new Error(observed.error.message), {
      operation: observed.operation, uncertain: observed.state === "unknown",
    });
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
};
const invokeOta = async (operation, payload, epoch) => {
  assertActivity(epoch);
  otaActivity.operation = operation;
  otaActivity.execution_id = null;
  renderOta();
  const accepted = await requestJson(`/fre3nder/api/v1/ota/${operation}`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Fre3nder-CSRF": csrfToken },
    body: JSON.stringify(payload),
  });
  assertActivity(epoch);
  otaActivity.execution_id = accepted.execution.id;
  try { return await waitExecution(accepted.execution, epoch); }
  catch (error) { error.accepted = true; throw error; }
};
const beginActivity = (kind) => {
  stopOtaPolling(); otaFailure = null;
  otaActivity = { operation: kind === "upload" ? "upload" : null };
  return ++otaEpoch;
};
const finishActivity = (epoch) => {
  if (epoch !== otaEpoch) return;
  otaActivity = null; renderOta(); scheduleOtaPoll();
};
const checkPackage = async () => {
  if (otaActivity || otaElement("check").disabled) return;
  const packageId = otaElement("package").value;
  const previous = otaState.execution;
  const epoch = beginActivity("check");
  localFileChanged = false;
  otaElement("file").value = "";
  otaPreflight = null;
  saveOtaReceipt({ package_id: packageId });
  try {
    if (!(previous && previous.package_id === packageId &&
      ((previous.operation === "verify" && previous.state === "succeeded") || previous.operation === "preflight"))) {
      verifiedPackageId = null;
      await invokeOta("verify", { package_id: packageId }, epoch);
      verifiedPackageId = packageId;
    }
    await invokeOta("preflight", { package_id: packageId }, epoch);
  } catch (error) { showOtaError(error); }
  finally { finishActivity(epoch); }
};
const confirmationText = (context, choices, continuing) => {
  const declined = ["home", "sys"].filter((role) => choices[role] === "none");
  return [
    continuing ? "Continue the recorded update? Completed steps will not be repeated." : "Update Fre3nder?",
    `${context.runtime.installed_version} → ${context.package.version}`,
    `Active slot ${context.runtime.active_slot} → target slot ${context.target.slot}`,
    continuing ? `Next step: ${operationLabel[nextOperation[context.state]]}.` : "",
    `HOME backup: ${choices.home === "none" ? "No backup" : choices.home.toUpperCase()}; SYS backup: ${choices.sys === "none" ? "No backup" : choices.sys.toUpperCase()}`,
    declined.length ? `WARNING: ${declined.map((role) => role.toUpperCase()).join(" and ")} backup explicitly declined.`
      : continuing ? "Completed backups will not be recreated." : "Selected backups will be created and verified before writing.",
    "HOME is preserved. SYS is reset when the updated system boots.",
    continuing ? "Only remaining steps will run: Kernel/RootFS writes if still required, readback, activation and restart."
      : "Kernel and RootFS will be written to the inactive system, readback verified, activated, and the printer restarted.",
    sameVersionNotice(context),
  ].filter(Boolean).join("\n\n");
};
const runUpdate = async () => {
  if (!canUpdate()) return;
  const existing = otaState.core.transaction;
  const context = existing || otaPreflight;
  const packageId = existing ? transactionPackageId(existing) : otaElement("package").value;
  const choices = currentChoices();
  if (!window.confirm(confirmationText(context, choices, Boolean(existing)))) return;
  const epoch = beginActivity("update");
  if (!existing) saveOtaReceipt({ package_id: packageId, ...choices });
  try {
    await loadOta();
    assertActivity(epoch);
    if (otaState.core.busy || (otaState.execution && ["running", "uploading", "unknown"].includes(otaState.execution.state))) throw new Error("Another operation is active or its outcome is unknown. Update paused.");
    let transaction = otaState.core.transaction;
    if (transaction && (!existing || transaction.transaction_id !== existing.transaction_id)) throw new Error("Another OTA transaction is active. Update paused.");
    if (!transaction) {
      const previous = otaState.execution;
      if (!(previous && previous.state === "succeeded" && previous.operation === "backup-plan"
        && previous.package_id === packageId && previous.home === choices.home && previous.sys === choices.sys)) {
        await invokeOta("backup-plan", { package_id: packageId, ...choices }, epoch);
      }
      await invokeOta("backup", { package_id: packageId, ...choices }, epoch);
      transaction = otaState.core.transaction;
      if (!transaction || transactionPackageId(transaction) !== packageId) throw new Error("Backup completed without the expected transaction. Update paused.");
      rememberTransaction(transaction);
      if (transaction.package.version !== context.package.version
          || transaction.runtime.installed_version !== context.runtime.installed_version
          || transaction.runtime.active_slot !== context.runtime.active_slot
          || transaction.target.slot !== context.target.slot) {
        throw new Error("The update context changed after confirmation. Review the recorded transaction and explicitly confirm continuation.");
      }
    }
    const transactionId = transaction.transaction_id;
    while (true) {
      assertActivity(epoch);
      const operation = nextOperation[transaction.state];
      if (!operation) throw new Error("Unrecognized Core phase. Inspect the printer before continuing.");
      const payload = operation === "reboot" ? { transaction_id: transactionId }
        : { package_id: packageId, transaction_id: transactionId };
      if (operation === "reboot") saveOtaReceipt({ ...otaReceipt, reboot_status: "pending" });
      try {
        const result = await invokeOta(operation, payload, epoch);
        if (operation === "reboot") saveOtaReceipt({ ...otaReceipt,
          reboot_status: result && result.state === "reboot-requested" && result.transaction_id === transactionId ? "requested" : "unclear",
        });
      }
      catch (error) {
        const rejected = (error.operation && !error.uncertain) || (error.rejected && !error.accepted);
        if (operation !== "reboot" || rejected) {
          if (operation === "reboot") saveOtaReceipt({ ...otaReceipt, reboot_status: null });
          throw error;
        }
        saveOtaReceipt({ ...otaReceipt, reboot_status: "unclear" });
      }
      if (operation === "reboot") break;
      transaction = otaState.core.transaction;
      if (!transaction || transaction.transaction_id !== transactionId) throw new Error("Transaction status changed or disappeared. Update paused without repeating a step.");
    }
  } catch (error) { showOtaError(error); }
  finally { finishActivity(epoch); }
};

const uploadPackage = async (event) => {
  event.preventDefault();
  if (otaActivity || otaElement("upload").disabled) return;
  const file = otaElement("file").files[0];
  if (!file || !file.name.endsWith(".ota") || file.size <= 0 || file.size > 96 * 1024 * 1024) {
    showOtaError(new Error("Select a .ota file between 1 byte and 96 MiB.")); return;
  }
  const epoch = beginActivity("upload");
  otaPreflight = null; verifiedPackageId = null; saveOtaReceipt(null);
  disableOtaControls();
  const progress = otaElement("upload-progress");
  progress.hidden = false; progress.value = 0;
  setText("ota-phase", "Uploading package…");
  try {
    const execution = await new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", "/fre3nder/api/v1/ota/upload");
      request.responseType = "json";
      request.setRequestHeader("Content-Type", "application/octet-stream");
      request.setRequestHeader("X-Fre3nder-CSRF", csrfToken);
      request.setRequestHeader("X-Fre3nder-Filename", encodeURIComponent(file.name));
      request.upload.onprogress = (update) => { if (update.lengthComputable) progress.value = update.loaded * 100 / update.total; };
      request.onload = () => {
        const data = request.response;
        if (request.status === 202 && data && data.api_version === 1 && data.ok === true) resolve(data.execution);
        else reject(Object.assign(new Error(data && data.error ? data.error.message : "OTA upload rejected."), { status: request.status }));
      };
      request.onerror = request.onabort = () => reject(new Error("Upload connection lost. Inspect server status before explicitly retrying."));
      request.send(file);
    });
    assertActivity(epoch);
    saveOtaReceipt({ package_id: execution.package_id });
    otaActivity.operation = "verify";
    otaActivity.execution_id = execution.id;
    progress.hidden = true;
    await waitExecution(execution, epoch); // Upload already started Verify; do not submit it twice.
    verifiedPackageId = execution.package_id;
    await invokeOta("preflight", { package_id: execution.package_id }, epoch);
    localFileChanged = false;
  } catch (error) { showOtaError(error); }
  finally {
    progress.hidden = true;
    try { await loadOta(); } catch (error) { handleStatusError(error); }
    finishActivity(epoch);
  }
};
document.getElementById("ota-upload-form").addEventListener("submit", uploadPackage);
otaElement("check").addEventListener("click", checkPackage);
otaElement("update").addEventListener("click", runUpdate);
otaElement("file").addEventListener("change", () => {
  if (otaActivity) return;
  localFileChanged = Boolean(otaElement("file").files[0]);
  saveOtaReceipt(null); renderOta();
});
otaElement("package").addEventListener("change", () => {
  if (otaActivity) return;
  otaPreflight = null; verifiedPackageId = null; otaFailure = null;
  saveOtaReceipt({ package_id: otaElement("package").value }); renderOta();
});
for (const role of ["home", "sys"]) otaElement(role).addEventListener("change", renderOta);
window.addEventListener("pagehide", () => { ++otaEpoch; otaActivity = null; stopOtaPolling(); });
window.addEventListener("pageshow", () => { if (csrfToken) loadOta().catch(handleStatusError); });

const renderNavigation = () => {
  const updates = window.location.hash === "#updates" || Boolean(rebootStatus());
  const appPage = !updates && window.location.hash === "#apps";
  document.getElementById("overview-view").hidden = updates || appPage;
  document.getElementById("updates-view").hidden = !updates;
  document.getElementById("apps-view").hidden = !appPage;
  for (const link of document.querySelectorAll("nav a")) {
    const active = link.getAttribute("href") === (updates ? "#updates" : appPage ? "#apps" : "#overview");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
};
window.addEventListener("hashchange", renderNavigation);
renderNavigation();
renderReboot();

if (!rebootStatus()) loadOverview().catch(() => {
  document.getElementById("error").hidden = false;
  setStatus("admin-status", "Unavailable", "neutral");
  setStatus("admin-status-sidebar", "Unavailable", "neutral");
});
