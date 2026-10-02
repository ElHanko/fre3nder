"use strict";

const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

const loadJson = async (path) => {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Accept": "application/json" },
  });
  const data = await response.json();
  if (!response.ok || data.ok !== true || data.api_version !== 1) {
    throw new Error("Management API request failed");
  }
  return data;
};

const loadOverview = async () => {
  const [systemResponse, maintenanceResponse] = await Promise.all([
    loadJson("/fre3nder/api/v1/system"),
    loadJson("/fre3nder/api/v1/maintenance"),
  ]);

  const system = systemResponse.system;
  const maintenance = maintenanceResponse.maintenance;

  setText("system-version", system.version);
  setText("root-status", system.root_status);
  setText(
    "maintenance-status",
    maintenance.enabled ? "enabled" : "disabled",
  );
  setText("web-status", maintenance.web_status);
};

loadOverview().catch(() => {
  const error = document.getElementById("error");
  error.hidden = false;
  error.textContent = "Management status is currently unavailable.";
});
