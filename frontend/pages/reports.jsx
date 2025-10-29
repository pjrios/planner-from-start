const API_BASE = window.location.origin;
const statusOutput = document.getElementById("reports-status");
const trimesterTableBody = document.querySelector("#trimester-table tbody");
const topicTableBody = document.querySelector("#topic-table tbody");
const reportButtons = document.querySelectorAll(".report-download");

const charts = {
  trimester: null,
  topic: null,
};

function setStatus(message, isError = false) {
  if (!statusOutput) return;
  statusOutput.textContent = message || "";
  statusOutput.dataset.state = isError ? "error" : "";
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

function renderTrimesterTable(rows) {
  if (!trimesterTableBody) return;
  trimesterTableBody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");

    const topics = row.topics
      .slice()
      .sort((a, b) => b.hours - a.hours)
      .slice(0, 3)
      .map((topic) => `${topic.topic} (${topic.hours}h)`)
      .join(", ");

    tr.innerHTML = `
      <td>${row.group}</td>
      <td>${row.trimester}</td>
      <td>${row.total_hours}</td>
      <td>${topics || "–"}</td>
    `;
    trimesterTableBody.appendChild(tr);
  });
}

function renderTopicTable(rows) {
  if (!topicTableBody) return;
  topicTableBody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const groupDetails = row.groups
      .map((group) => `${group.group} (${group.hours}h)`)
      .join(", ");

    tr.innerHTML = `
      <td>${row.topic}</td>
      <td>${row.total_hours}</td>
      <td>${groupDetails || "–"}</td>
    `;
    topicTableBody.appendChild(tr);
  });
}

function buildTrimesterChart(rows) {
  const canvas = document.getElementById("trimester-hours-chart");
  if (!canvas || !window.Chart) return;

  const labels = rows.map((row) => `${row.group} – ${row.trimester}`);
  const data = rows.map((row) => row.total_hours);

  charts.trimester?.destroy?.();
  charts.trimester = new window.Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Total hours",
          data,
          backgroundColor: "rgba(59, 130, 246, 0.6)",
          borderColor: "rgba(37, 99, 235, 1)",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            precision: 0,
          },
        },
      },
    },
  });
}

function buildTopicChart(rows) {
  const canvas = document.getElementById("topic-hours-chart");
  if (!canvas || !window.Chart) return;

  const labels = rows.map((row) => row.topic);
  const data = rows.map((row) => row.total_hours);

  charts.topic?.destroy?.();
  charts.topic = new window.Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: "Total hours",
          data,
          backgroundColor: [
            "rgba(14, 165, 233, 0.7)",
            "rgba(129, 140, 248, 0.7)",
            "rgba(236, 72, 153, 0.7)",
            "rgba(16, 185, 129, 0.7)",
            "rgba(251, 191, 36, 0.7)",
          ],
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#e2e8f0",
          },
        },
      },
    },
  });
}

async function downloadReport(report, format, button) {
  try {
    button.disabled = true;
    setStatus(`Preparing ${report} report…`);
    const response = await fetch(
      `${API_BASE}/reports/${report}?format=${format}`
    );
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Download failed (${response.status})`);
    }
    const blob = await response.blob();
    const extension = format === "csv" ? "csv" : "pdf";
    const filename = `${report}_report.${extension}`;
    if (window.saveAs) {
      window.saveAs(blob, filename);
    } else {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
    }
    setStatus(`${format.toUpperCase()} download ready.`);
  } catch (error) {
    console.error(error);
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function attachDownloadHandlers() {
  reportButtons.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const report = button.dataset.report;
      const format = button.dataset.format;
      downloadReport(report, format, button);
    });
  });
}

async function bootstrapReports() {
  if (!statusOutput) return;
  try {
    setStatus("Loading reports…");
    const [trimester, topic] = await Promise.all([
      fetchJson("/reports/trimester"),
      fetchJson("/reports/topic"),
    ]);
    const trimesterRows = trimester.rows || [];
    const topicRows = topic.rows || [];
    renderTrimesterTable(trimesterRows);
    renderTopicTable(topicRows);
    buildTrimesterChart(trimesterRows);
    buildTopicChart(topicRows);
    setStatus("Reports updated.");
  } catch (error) {
    console.error(error);
    setStatus(error.message, true);
  }
}

attachDownloadHandlers();
bootstrapReports();
