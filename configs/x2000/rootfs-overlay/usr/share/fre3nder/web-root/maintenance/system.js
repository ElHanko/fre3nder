"use strict";

let systemLoading = false;
let systemEpoch = 0;
const systemElement = (name) => document.getElementById(`system-${name}`);
const systemValue = (value) => value === null || value === undefined ? "Unavailable" : String(value);
const systemBytes = (value) => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "Unavailable";
  return value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GiB` : `${(value / 1024 ** 2).toFixed(1)} MiB`;
};
const systemUptime = (value) => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "Unavailable";
  const seconds = Math.floor(value);
  return `${Math.floor(seconds / 86400)}d ${Math.floor(seconds / 3600) % 24}h ${Math.floor(seconds / 60) % 60}m ${seconds % 60}s`;
};
const systemNode = (tag, value, className) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = systemValue(value);
  if (className) node.className = className;
  return node;
};
const systemStatus = (value, confirmed = true) => systemNode("span", value,
  `status status-${confirmed && ["active", "running", "up", "enabled"].includes(value) ? "ok"
    : value && /failed|timeout|not-running|^down$/.test(value) ? "error" : "neutral"}`);
const systemRows = (target, rows) => {
  target.replaceChildren();
  for (const [label, value] of rows) {
    const row = systemNode("div");
    const detail = systemNode("dd");
    if (value && typeof value === "object") detail.append(value);
    else detail.textContent = systemValue(value);
    row.append(systemNode("dt", label), detail);
    target.append(row);
  }
};
const systemMeter = (used, total, label) => {
  if (typeof used !== "number" || typeof total !== "number" || !Number.isFinite(used) || !Number.isFinite(total)
      || total <= 0 || used < 0 || used > total) return "Unavailable";
  const group = systemNode("div", undefined, "system-usage");
  const meter = systemNode("meter");
  meter.min = 0; meter.max = total; meter.value = used;
  meter.setAttribute("aria-label", label);
  const percent = `${(used / total * 100).toFixed(1)}%`;
  meter.textContent = percent;
  group.append(meter, systemNode("span", percent));
  return group;
};
const systemCard = (target, title, rows) => {
  const card = systemNode("article", undefined, "system-group");
  const list = systemNode("dl", undefined, "status-list");
  systemRows(list, rows);
  card.append(systemNode("h3", title), list);
  target.append(card);
};
const systemSelection = (value) => !value || value.status === "unavailable" ? "Unavailable"
  : value.status === "none" ? "None selected" : systemValue(value.name);

const systemRender = (data) => {
  const platform = data.platform || {}, runtime = data.runtime || {}, memory = data.memory || {};
  const boot = data.boot || {}, network = data.network || {}, apps = data.applications || {};
  const maintenance = data.maintenance || {}, ota = maintenance.ota;
  systemRows(systemElement("platform"), [
    ["Fre3nder version", platform.version], ["Hardware model", platform.hardware_model],
    ["CPU model", platform.cpu_model], ["Architecture", platform.architecture],
    ["Kernel version", platform.kernel_version], ["Hostname", platform.hostname],
  ]);
  systemRows(systemElement("runtime"), [
    ["Uptime", systemUptime(runtime.uptime_seconds)], ["System time (UTC)", runtime.system_time],
    ["Load average (1 / 5 / 15 min)", runtime.load_average ? runtime.load_average.map((value) => value.toFixed(2)).join(" / ") : null],
  ]);
  systemRows(systemElement("memory"), [
    ["Total RAM", systemBytes(memory.total_bytes)], ["Available RAM", systemBytes(memory.available_bytes)],
    ["Used RAM", systemBytes(memory.used_bytes)], ["RAM usage", systemMeter(memory.used_bytes, memory.total_bytes, "RAM usage")],
    ["Total swap", systemBytes(memory.swap_total_bytes)], ["Free swap", systemBytes(memory.swap_free_bytes)],
    ["Used swap", systemBytes(memory.swap_used_bytes)],
  ]);
  systemElement("storage").replaceChildren();
  if (!data.storage || !data.storage.length) systemElement("storage").textContent = "Unavailable";
  for (const item of data.storage || []) systemCard(systemElement("storage"), item.role, [
    ["Logical storage target", item.role], ["Block device", item.device], ["Filesystem", item.filesystem],
    ["Mountpoint", item.mountpoint], ["Total", systemBytes(item.total_bytes)],
    ["Used", systemBytes(item.used_bytes)], ["Available", systemBytes(item.available_bytes)],
    ["Usage", systemMeter(item.used_bytes, item.total_bytes, `${item.role} usage`)],
  ]);
  systemRows(systemElement("boot"), [
    ["Active A/B slot", boot.active_slot], ["Active RootFS", boot.active_rootfs],
    ["Persistent root", systemStatus(boot.root_status)],
  ]);
  const route = network.default_ipv4_route;
  systemRows(systemElement("network-route"), [["Default IPv4 route", route
    ? `${route.interface} via ${route.gateway} (metric ${route.metric})`
    : network.default_ipv4_routes && network.default_ipv4_routes.length === 0 ? "No default IPv4 route" : "Unavailable"]]);
  systemElement("network").replaceChildren();
  if (network.interfaces === null || network.interfaces === undefined) systemElement("network").textContent = "Unavailable";
  else if (!network.interfaces.length) systemElement("network").textContent = "No Ethernet or WLAN interfaces detected.";
  for (const item of network.interfaces || []) systemCard(systemElement("network"), item.name, [
    ["Type", item.kind === "wlan" ? "WLAN" : "Ethernet"], ["Link state", systemStatus(item.state)],
    ["Carrier", typeof item.carrier !== "boolean" ? "Unavailable" : item.carrier ? "Connected" : "Disconnected"],
    ["IP addresses", !item.addresses ? "Unavailable" : item.addresses.length ? item.addresses.join(", ") : "None assigned"],
  ]);
  systemElement("usb").replaceChildren();
  systemElement("usb-count").textContent = data.usb === null || data.usb === undefined ? "Unavailable" : `${data.usb.length} USB devices detected.`;
  for (const item of data.usb || []) systemCard(systemElement("usb"), item.product, [
    ["Manufacturer", item.manufacturer], ["Vendor / product ID", `${systemValue(item.vendor_id)} / ${systemValue(item.product_id)}`],
    ["USB connection", item.port], ["Parent connection", item.parent || (item.port.startsWith("usb") ? "Root hub" : null)],
    ["Device driver", item.driver], ["Interface drivers", item.interfaces.length
      ? item.interfaces.map((part) => `${part.interface}: ${systemValue(part.driver)}`).join(", ") : "No interfaces reported"],
  ]);
  systemRows(systemElement("services"), data.services && data.services.length
    ? data.services.map((item) => [item.name, systemStatus(item.status, item.process_running === true)]) : [["Service status", null]]);
  systemRows(systemElement("applications"), [
    ["Installed .fre3app packages", apps.installed_count], ["Selected web frontend", systemSelection(apps.web_frontend)],
    ["Selected display frontend", systemSelection(apps.display_frontend)],
    ["Display manager status (recorded)", systemStatus(apps.display_runtime_status, false)],
  ]);
  systemRows(systemElement("maintenance"), [
    ["Maintenance", systemStatus(maintenance.enabled === null || maintenance.enabled === undefined ? null : maintenance.enabled ? "enabled" : "disabled")],
    ["Maintenance web status (recorded)", systemStatus(maintenance.web_status, false)],
    ["OTA busy", ota ? ota.busy ? "Yes" : "No" : null],
    ["Pending update", ota ? ota.transaction ? ota.transaction.state : "No pending update" : null],
    ["Update activation", ota ? ota.activation ? ota.activation.state : "None recorded" : null],
    ["Last validated update", ota && ota.known_good ? ota.known_good.version : null],
    ["Last OTA operation receipt", maintenance.execution ? `${maintenance.execution.operation}: ${maintenance.execution.state}` : "None recorded"],
  ]);
};

const systemAuthChanged = (authenticated) => {
  if (!authenticated) {
    ++systemEpoch;
    systemLoading = false;
    systemElement("information").hidden = true;
    for (const name of ["platform", "runtime", "memory", "storage", "boot", "network-route", "network", "usb", "services", "applications", "maintenance"]) {
      systemElement(name).replaceChildren();
    }
    systemElement("usb-count").textContent = "";
    systemElement("info-status").textContent = "";
    systemElement("info-error").hidden = true;
    systemElement("information").setAttribute("aria-busy", "false");
  }
  systemElement("locked").hidden = authenticated;
  systemElement("refresh").disabled = !authenticated || systemLoading;
  if (authenticated && !document.getElementById("system-view").hidden) systemLoad();
};

const systemLoad = async () => {
  if (!csrfToken || systemLoading) return;
  const epoch = ++systemEpoch;
  systemLoading = true;
  systemElement("refresh").disabled = true;
  systemElement("info-error").hidden = true;
  systemElement("info-status").textContent = "Loading system information…";
  systemElement("information").setAttribute("aria-busy", "true");
  try {
    const response = await requestJson("/fre3nder/api/v1/system/details");
    if (epoch !== systemEpoch) return;
    systemRender(response.system);
    systemElement("information").hidden = false;
    systemElement("info-status").textContent = "Current snapshot loaded. Use Refresh to update.";
  } catch (error) {
    if (epoch !== systemEpoch) return;
    systemElement("information").hidden = true;
    systemElement("info-status").textContent = "System information is unavailable.";
    systemElement("info-error").textContent = error.message;
    systemElement("info-error").hidden = false;
    if (error.status === 401) renderAuth({authenticated: false});
  } finally {
    if (epoch === systemEpoch) {
      systemLoading = false;
      systemElement("refresh").disabled = !csrfToken;
      systemElement("information").setAttribute("aria-busy", "false");
    }
  }
};
systemElement("refresh").addEventListener("click", systemLoad);
if (window.location.hash === "#system") systemLoad();
