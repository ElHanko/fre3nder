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
    throw new Error("Management API returned an invalid response.");
  }

  if (!response.ok || data.ok !== true || data.api_version !== 1) {
    const apiError = data && data.error;
    const message =
      apiError && typeof apiError.message === "string"
        ? apiError.message
        : "Management API request failed.";
    throw new Error(message);
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

loadOverview().catch(() => {
  document.getElementById("error").hidden = false;
  setStatus("admin-status", "Unavailable", "neutral");
  setStatus("admin-status-sidebar", "Unavailable", "neutral");
});
