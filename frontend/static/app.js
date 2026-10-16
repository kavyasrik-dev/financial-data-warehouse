"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const numberFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const statusColors = {
  success: "#267a55",
  failed: "#c25252",
  pending: "#c97e22",
};

let selectedDays = 30;
let requestController = null;

const byId = (id) => document.getElementById(id);
const totalTransactions = byId("totalTransactions");
const successRate = byId("successRate");
const failedTransactions = byId("failedTransactions");
const activeCustomers = byId("activeCustomers");
const customerCoverage = byId("customerCoverage");
const averageDaily = byId("averageDaily");
const transactionRange = byId("transactionRange");
const trendRange = byId("trendRange");
const errorBanner = byId("errorBanner");
const refreshButton = byId("refreshButton");

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function titleCase(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value, options = { month: "short", day: "numeric" }) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Not available";
  return parsed.toLocaleDateString(undefined, options);
}

function setExternalLink(element, value) {
  try {
    const url = new URL(value);
    if (url.protocol === "http:" || url.protocol === "https:") {
      element.href = url.toString();
      return;
    }
  } catch (error) {
    console.warn("Invalid console URL", error);
  }
  element.removeAttribute("href");
}

function renderMetrics(data) {
  const metrics = data.metrics;
  totalTransactions.textContent = integerFormatter.format(metrics.total_transactions || 0);
  successRate.textContent = `${numberFormatter.format(metrics.success_rate || 0)}%`;
  failedTransactions.textContent = `${integerFormatter.format(metrics.failed_transactions || 0)} failed transactions`;
  activeCustomers.textContent = integerFormatter.format(metrics.active_customers || 0);
  customerCoverage.textContent = `${integerFormatter.format(metrics.total_customers || 0)} total customers`;
  averageDaily.textContent = numberFormatter.format(metrics.average_daily_transactions || 0);
  transactionRange.textContent = `Last ${data.range_days} days`;
  trendRange.textContent = `Last ${data.range_days} days`;
  byId("dataThrough").textContent = metrics.data_through
    ? `Data through ${formatDate(metrics.data_through, { month: "short", day: "numeric", year: "numeric" })}`
    : "No activity loaded";
}

function renderTrend(rows) {
  const chart = byId("trendChart");
  const empty = byId("trendEmpty");
  chart.replaceChildren();
  if (!rows.length) {
    chart.hidden = true;
    empty.hidden = false;
    return;
  }
  chart.hidden = false;
  empty.hidden = true;

  const width = 800;
  const height = 280;
  const padding = { top: 22, right: 20, bottom: 36, left: 48 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...rows.map((row) => Number(row.total_transactions)), 1);
  const yMax = Math.ceil(maxValue / 10) * 10 || 10;

  for (let index = 0; index <= 4; index += 1) {
    const y = padding.top + (innerHeight * index) / 4;
    chart.append(svgElement("line", { x1: padding.left, y1: y, x2: width - padding.right, y2: y, class: "chart-grid" }));
    const label = svgElement("text", { x: padding.left - 10, y: y + 4, class: "chart-axis-label", "text-anchor": "end" });
    label.textContent = integerFormatter.format(yMax * (1 - index / 4));
    chart.append(label);
  }

  const points = rows.map((row, index) => {
    const x = padding.left + (rows.length === 1 ? innerWidth / 2 : (innerWidth * index) / (rows.length - 1));
    const y = padding.top + innerHeight - (Number(row.total_transactions) / yMax) * innerHeight;
    return { x, y, row };
  });

  const linePath = points.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");
  const areaPath = `${linePath} L${points.at(-1).x},${padding.top + innerHeight} L${points[0].x},${padding.top + innerHeight} Z`;
  chart.append(svgElement("path", { d: areaPath, class: "chart-area" }));
  chart.append(svgElement("path", { d: linePath, class: "chart-line" }));

  const labelIndexes = new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1]);
  points.forEach((point, index) => {
    if (rows.length <= 14 || index % Math.max(1, Math.ceil(rows.length / 14)) === 0 || index === rows.length - 1) {
      const circle = svgElement("circle", { cx: point.x, cy: point.y, r: 3.5, class: "chart-point" });
      const title = svgElement("title");
      title.textContent = `${formatDate(point.row.full_date)}: ${integerFormatter.format(point.row.total_transactions)} transactions`;
      circle.append(title);
      chart.append(circle);
    }
    if (labelIndexes.has(index)) {
      const label = svgElement("text", {
        x: point.x,
        y: height - 10,
        class: "chart-axis-label",
        "text-anchor": index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle",
      });
      label.textContent = formatDate(point.row.full_date);
      chart.append(label);
    }
  });
}

function renderStatus(rows) {
  const chart = byId("statusChart");
  const legend = byId("statusLegend");
  chart.replaceChildren();
  legend.replaceChildren();

  const total = rows.reduce((sum, row) => sum + Number(row.total_transactions), 0);
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  chart.append(svgElement("circle", { cx: 90, cy: 90, r: radius, class: "donut-track" }));

  let offset = 0;
  rows.forEach((row) => {
    const count = Number(row.total_transactions);
    const length = total ? (count / total) * circumference : 0;
    const color = statusColors[row.transaction_status] || "#718078";
    chart.append(
      svgElement("circle", {
        cx: 90,
        cy: 90,
        r: radius,
        class: "donut-segment",
        stroke: color,
        "stroke-dasharray": `${length} ${circumference - length}`,
        "stroke-dashoffset": -offset,
      }),
    );
    offset += length;

    const legendRow = document.createElement("div");
    legendRow.className = "legend-row";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.backgroundColor = color;
    const name = document.createElement("span");
    name.className = "legend-name";
    name.textContent = titleCase(row.transaction_status);
    const value = document.createElement("span");
    value.className = "legend-value";
    value.textContent = total ? `${numberFormatter.format((count / total) * 100)}%` : "0%";
    legendRow.append(swatch, name, value);
    legend.append(legendRow);
  });

  const value = svgElement("text", { x: 90, y: 88, class: "donut-value" });
  value.textContent = integerFormatter.format(total);
  const label = svgElement("text", { x: 90, y: 106, class: "donut-label" });
  label.textContent = "transactions";
  chart.append(value, label);
}

function renderCategories(rows) {
  const container = byId("categoryBars");
  container.replaceChildren();
  const maximum = Math.max(...rows.map((row) => Number(row.total_transactions)), 1);
  rows.forEach((row) => {
    const wrapper = document.createElement("div");
    wrapper.className = "bar-row";
    const label = document.createElement("span");
    label.className = "bar-label";
    label.textContent = titleCase(row.merchant_category);
    const value = document.createElement("span");
    value.className = "bar-value";
    value.textContent = integerFormatter.format(row.total_transactions);
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${Math.max(2, (Number(row.total_transactions) / maximum) * 100)}%`;
    track.append(fill);
    wrapper.append(label, value, track);
    container.append(wrapper);
  });
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No category activity is available.";
    container.append(empty);
  }
}

function renderCustomers(rows) {
  const body = byId("customerRows");
  const empty = byId("customerEmpty");
  body.replaceChildren();
  empty.hidden = Boolean(rows.length);
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const status = String(row.customer_status || "unknown").toLowerCase();
    const total = Number(row.total_transactions) || 0;
    const successful = Number(row.successful_transactions) || 0;
    const values = [
      row.customer_name_masked || "Masked customer",
      [row.city, row.country].filter(Boolean).join(", ") || "Not available",
      titleCase(status),
      integerFormatter.format(total),
      total ? `${numberFormatter.format((successful / total) * 100)}%` : "0%",
      formatDate(row.last_transaction_at, { month: "short", day: "numeric", year: "numeric" }),
    ];
    values.forEach((value, index) => {
      const cell = document.createElement("td");
      if (index === 2) {
        const badge = document.createElement("span");
        badge.className = `customer-status ${status === "active" ? "active" : "inactive"}`;
        badge.textContent = value;
        cell.append(badge);
      } else {
        cell.textContent = value;
      }
      if (index === 3 || index === 4) cell.className = "numeric";
      tr.append(cell);
    });
    body.append(tr);
  });
}

function render(data) {
  renderMetrics(data);
  renderTrend(data.daily || []);
  renderStatus(data.statuses || []);
  renderCategories(data.categories || []);
  renderCustomers(data.customers || []);
  setExternalLink(byId("airflowLink"), data.links?.airflow);
  setExternalLink(byId("metabaseLink"), data.links?.metabase);
  byId("lastUpdated").textContent = `Updated ${new Date(data.generated_at).toLocaleString()}`;
}

async function loadDashboard() {
  requestController?.abort();
  requestController = new AbortController();
  const timeout = window.setTimeout(() => requestController.abort(), 12000);
  refreshButton.disabled = true;
  refreshButton.textContent = "Loading";
  errorBanner.hidden = true;
  try {
    const response = await fetch(`/api/overview?days=${selectedDays}`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal: requestController.signal,
    });
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    render(await response.json());
  } catch (error) {
    if (error.name !== "AbortError") console.error(error);
    errorBanner.hidden = false;
  } finally {
    window.clearTimeout(timeout);
    refreshButton.disabled = false;
    refreshButton.textContent = "Refresh";
  }
}

document.querySelectorAll("[data-days]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedDays = Number(button.dataset.days);
    document.querySelectorAll("[data-days]").forEach((candidate) => {
      candidate.classList.toggle("selected", candidate === button);
    });
    loadDashboard();
  });
});

refreshButton.addEventListener("click", loadDashboard);
loadDashboard();
