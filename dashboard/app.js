const colors = {
  emergency: "#ff2a5f",
  critical: "#ff8c00",
  clinical: "#00d2ff",
  routine: "#39ff14",
};

const labels = {
  emergency: "Emergency",
  critical: "Critical",
  clinical: "Clinical",
  routine: "Routine",
};

const nodePositions = {
  "ward-a": [120, 120],
  "ward-b": [120, 250],
  icu: [120, 380],
  lab: [300, 380],
  "edge-1": [360, 180],
  "edge-2": [360, 330],
  "core-1": [610, 205],
  "core-2": [610, 340],
  controller: [850, 145],
  "ehr-server": [870, 330],
};

const animation = {
  playing: true,
  speed: 1.25,
  frame: null,
  startedAt: performance.now(),
  classFilter: "all",
};

async function loadData() {
  const response = await fetch("/data/latest_summary.json");
  if (!response.ok) throw new Error("Run the Python experiment before opening the dashboard.");
  return response.json();
}

async function loadFifoData() {
  const response = await fetch("/data/latest_summary_fifo.json");
  if (!response.ok) return null;
  return response.json();
}

async function runExperiment() {
  const useRLCheckbox = document.getElementById("useRLCheckbox");
  const params = new URLSearchParams({
    scenario: document.getElementById("scenarioSelect").value,
    policy: document.getElementById("policySelect").value,
    seed: document.getElementById("seedInput").value,
    duration: document.getElementById("durationInput").value,
    use_rl: useRLCheckbox ? useRLCheckbox.checked : false,
  });
  const response = await fetch(`/api/run?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "Experiment failed.");
  }
  return payload.data;
}

function renderMetrics(summary) {
  const threshold = summary.stability_threshold_load;
  document.getElementById("threshold").textContent = threshold
    ? `Unstable from ${threshold}x load`
    : "Stable across tested loads";

  const critical = summary.final_load_metrics.critical;
  let metricsHTML = [
    ["Policy", summary.policy],
    ["Scenario", summary.scenario],
    ["Critical P95 latency", `${critical.p95_latency_ms} ms`],
    ["Critical loss", `${critical.loss_pct}%`],
    ["Degradation index", summary.degradation.at(-1).index],
  ].map(([name, value]) => `<div class="metric"><span>${name}</span><strong>${value}</strong></div>`).join("");

  if (summary.final_class_weights) {
    const weightsStr = Object.entries(summary.final_class_weights).map(([k,v]) => `${labels[k]||k}:${v}`).join(", ");
    metricsHTML += `<div class="metric" style="background: rgba(52, 211, 153, 0.1); border-color: rgba(52, 211, 153, 0.3);"><span>RL Queue Weights</span><strong style="color: #34d399; font-size: 14px;">${weightsStr}</strong></div>`;
  }
  document.getElementById("metrics").innerHTML = metricsHTML;
}

function renderPaths(paths) {
  const container = document.getElementById("paths");
  container.innerHTML = paths
    .map(([path, count]) => `<div class="path"><span>${path}</span><strong>${count}</strong></div>`)
    .join("");
}

function renderRules(rules) {
  const container = document.getElementById("rules");
  container.innerHTML = rules
    .slice(0, 8)
    .map((rule) => `<div class="rule"><strong>${rule.class}</strong><span>${rule.match}</span><code>${rule.action}</code></div>`)
    .join("");
}

function renderHotLinks(links) {
  const container = document.getElementById("hotLinks");
  container.innerHTML = links
    .slice(0, 6)
    .map((link) => {
      const util = Math.round(link.peak_utilization * 100);
      return `<div class="path"><span>${link.a} -> ${link.b}</span><strong>${util}% peak</strong></div>`;
    })
    .join("");
}

function renderComparison(prioritySummary, fifoSummary) {
  const container = document.getElementById("comparison");
  if (!fifoSummary) {
    container.innerHTML = '<div class="comparison-card"><span>FIFO baseline</span><strong>Run ./run_experiment.sh</strong></div>';
    return;
  }
  const priorityCritical = prioritySummary.final_load_metrics.critical;
  const fifoCritical = fifoSummary.final_load_metrics.critical;
  const latencyGain = fifoCritical.p95_latency_ms
    ? ((1 - priorityCritical.p95_latency_ms / fifoCritical.p95_latency_ms) * 100).toFixed(1)
    : "0.0";
  const lossGain = fifoCritical.loss_pct ? ((1 - priorityCritical.loss_pct / fifoCritical.loss_pct) * 100).toFixed(1) : "0.0";
  const cards = [
    ["Priority threshold", `${prioritySummary.stability_threshold_load || "stable"}x`],
    ["FIFO threshold", `${fifoSummary.stability_threshold_load || "stable"}x`],
    ["Critical latency improvement", `${latencyGain}%`],
    ["Critical loss improvement", `${lossGain}%`],
  ];
  container.innerHTML = cards
    .map(([label, value]) => `<div class="comparison-card"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function populateLoadSelect(runs) {
  const select = document.getElementById("loadSelect");
  select.innerHTML = runs.map((run, index) => `<option value="${index}">${run.load}x load</option>`).join("");
  select.value = String(runs.length - 1);
}

function drawChart(runs, metric) {
  const canvas = document.getElementById("chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const pad = 56;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "rgba(0, 0, 0, 0)";
  ctx.fillRect(0, 0, w, h);

  const loads = runs.map((run) => run.load);
  const values = runs.flatMap((run) => Object.values(run.classes).map((cls) => cls[metric]));
  const xMin = Math.min(...loads);
  const xMax = Math.max(...loads);
  const yMin = metric === "delivery_ratio" ? Math.min(0.75, Math.min(...values)) : 0;
  const yMax = Math.max(...values, metric === "delivery_ratio" ? 1 : 10) * 1.08;

  const x = (load) => pad + ((load - xMin) / (xMax - xMin || 1)) * (w - pad * 2);
  const y = (value) => h - pad - ((value - yMin) / (yMax - yMin || 1)) * (h - pad * 2);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const gy = pad + i * ((h - pad * 2) / 4);
    ctx.beginPath();
    ctx.moveTo(pad, gy);
    ctx.lineTo(w - pad, gy);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
  ctx.beginPath();
  ctx.moveTo(pad, pad);
  ctx.lineTo(pad, h - pad);
  ctx.lineTo(w - pad, h - pad);
  ctx.stroke();

  for (const cls of ["emergency", "critical", "clinical", "routine"]) {
    if (!runs[0].classes[cls]) continue;
    ctx.strokeStyle = colors[cls];
    ctx.lineWidth = 4;
    ctx.shadowColor = colors[cls];
    ctx.shadowBlur = 8;
    ctx.beginPath();
    runs.forEach((run, index) => {
      const px = x(run.load);
      const py = y(run.classes[cls][metric]);
      if (index === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    const last = runs.at(-1);
    ctx.fillStyle = colors[cls];
    ctx.font = "700 15px 'Outfit', system-ui";
    ctx.fillText(labels[cls], x(last.load) + 10, y(last.classes[cls][metric]) + 5);
  }

  ctx.fillStyle = "#94a3b8";
  ctx.font = "600 13px 'Outfit', system-ui";
  ctx.fillText("offered load multiplier", w / 2 - 70, h - 18);
  ctx.save();
  ctx.translate(18, h / 2 + 56);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(metric.replaceAll("_", " "), 0, 0);
  ctx.restore();
}

function interpolatePath(path, progress) {
  const points = path.map((node) => nodePositions[node]).filter(Boolean);
  if (points.length < 2) return null;
  const segments = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[i + 1];
    const length = Math.hypot(x2 - x1, y2 - y1);
    segments.push({ x1, y1, x2, y2, length });
    total += length;
  }
  let target = progress * total;
  for (const segment of segments) {
    if (target <= segment.length) {
      const t = target / Math.max(segment.length, 1);
      return {
        x: segment.x1 + (segment.x2 - segment.x1) * t,
        y: segment.y1 + (segment.y2 - segment.y1) * t,
      };
    }
    target -= segment.length;
  }
  const [x, y] = points.at(-1);
  return { x, y };
}

function packetCountFor(run, cls) {
  const generated = run.classes[cls]?.generated || 0;
  const base = cls === "emergency" ? 4 : cls === "critical" ? 3 : cls === "clinical" ? 2 : 1;
  return Math.max(base, Math.min(11, Math.round(generated / 180)));
}

function animatedPackets(run, elapsedSeconds) {
  return run.flow_rules.flatMap((rule, ruleIndex) => {
    if (animation.classFilter !== "all" && rule.class !== animation.classFilter) return [];
    
    // Dynamic speeds based on traffic class priority!
    let classSpeedMultiplier = 1.0;
    if (rule.class === "emergency") classSpeedMultiplier = 2.5;
    else if (rule.class === "critical") classSpeedMultiplier = 1.5;
    else if (rule.class === "clinical") classSpeedMultiplier = 0.8;
    else if (rule.class === "routine") classSpeedMultiplier = 0.4;
    
    const count = packetCountFor(run, rule.class);
    return Array.from({ length: count }, (_, packetIndex) => {
      // Create bursts of packets rather than perfectly uniform spacing
      const spacing = (packetIndex / count) + (Math.sin(packetIndex) * 0.05);
      const phase = (ruleIndex * 0.173 + spacing + elapsedSeconds * animation.speed * 0.16 * classSpeedMultiplier) % 1;
      return { rule, phase: phase < 0 ? phase + 1 : phase };
    });
  });
}

function drawPackets(ctx, run, elapsedSeconds) {
  for (const packet of animatedPackets(run, elapsedSeconds)) {
    const point = interpolatePath(packet.rule.path, packet.phase);
    if (!point) continue;
    const radius = packet.rule.class === "emergency" ? 8 : packet.rule.class === "critical" ? 6.5 : packet.rule.class === "clinical" ? 5 : 4;
    ctx.beginPath();
    ctx.fillStyle = colors[packet.rule.class];
    ctx.shadowColor = colors[packet.rule.class];
    ctx.shadowBlur = packet.rule.class === "emergency" ? 15 : packet.rule.class === "critical" ? 10 : 5;
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}

function drawTopology(run, elapsedSeconds = 0) {
  const canvas = document.getElementById("topology");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "rgba(0, 0, 0, 0)";
  ctx.fillRect(0, 0, w, h);

  ctx.fillStyle = "#e2e8f0";
  ctx.font = "700 16px 'Outfit', system-ui";
  ctx.fillText(`Controller policy: ${run.policy} | offered load: ${run.load}x`, 28, 34);

  for (const link of run.link_stats) {
    const a = nodePositions[link.a];
    const b = nodePositions[link.b];
    if (!a || !b) continue;
    
    if (link.is_failed) {
      ctx.strokeStyle = "#ff2a5f";
      ctx.setLineDash([6, 6]);
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.6;
      ctx.shadowBlur = 0;
    } else {
      const util = link.peak_utilization;
      const hue = 145 - util * 130;
      ctx.strokeStyle = `hsla(${hue}, 80%, 60%, 0.8)`;
      ctx.lineWidth = 2 + util * 6;
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
      ctx.shadowColor = ctx.strokeStyle;
      ctx.shadowBlur = util > 0.4 ? util * 15 : 0;
    }
    
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.stroke();
    
    ctx.setLineDash([]);
    ctx.shadowBlur = 0;

    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(11, 14, 20, 0.9)";
    ctx.fillRect(mx - 28, my - 13, 56, 20);
    ctx.strokeStyle = link.is_failed ? "#ff2a5f" : "rgba(255, 255, 255, 0.15)";
    ctx.lineWidth = 1;
    ctx.strokeRect(mx - 28, my - 13, 56, 20);
    ctx.fillStyle = link.is_failed ? "#ff2a5f" : "#e2e8f0";
    ctx.font = "600 12px 'Outfit', system-ui";
    ctx.fillText(link.is_failed ? "FAIL" : `${Math.round((link.peak_utilization || 0) * 100)}%`, mx - 14, my + 2);
  }

  drawPackets(ctx, run, elapsedSeconds);

  for (const [name, [x, y]] of Object.entries(nodePositions)) {
    const isController = name === "controller";
    const isServer = name === "ehr-server";
    ctx.fillStyle = isController ? "#3b82f6" : isServer ? "#475569" : "#1e293b";
    ctx.strokeStyle = isController || isServer ? "#60a5fa" : "rgba(255, 255, 255, 0.2)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, isController || isServer ? 24 : 20, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 12px 'Outfit', system-ui";
    ctx.textAlign = "center";
    ctx.fillText(name, x, y + 4);
    ctx.textAlign = "start";
  }
}

function currentRun() {
  if (!window.currentRuns) return null;
  const index = Number(document.getElementById("loadSelect").value || window.currentRuns.length - 1);
  return window.currentRuns[index];
}

function animateTopology(now) {
  const run = currentRun();
  if (run) drawTopology(run, (now - animation.startedAt) / 1000);
  animation.frame = requestAnimationFrame(animateTopology);
}

function restartAnimation() {
  if (animation.frame) cancelAnimationFrame(animation.frame);
  if (animation.playing) {
    animation.frame = requestAnimationFrame(animateTopology);
    return;
  }
  const run = currentRun();
  if (run) drawTopology(run, 0);
}

function renderDashboard({ summary, runs }, fifoData = null) {
  renderMetrics(summary);
  renderPaths(summary.dominant_paths_at_final_load);
  renderRules(summary.flow_rules_at_final_load);
  renderHotLinks(summary.hot_links_at_final_load);
  renderComparison(summary, fifoData?.summary || window.fifoSummary || null);
  populateLoadSelect(runs);
  drawChart(runs, document.getElementById("metricSelect").value);
  window.currentRuns = runs;
  restartAnimation();
}

document.getElementById("metricSelect").addEventListener("change", (event) => {
  if (window.currentRuns) drawChart(window.currentRuns, event.target.value);
});

document.getElementById("loadSelect").addEventListener("change", (event) => {
  if (window.currentRuns && !animation.playing) drawTopology(window.currentRuns[Number(event.target.value)]);
});

document.getElementById("packetClassSelect").addEventListener("change", (event) => {
  animation.classFilter = event.target.value;
});

document.getElementById("speedRange").addEventListener("input", (event) => {
  animation.speed = Number(event.target.value);
});

document.getElementById("playButton").addEventListener("click", (event) => {
  animation.playing = !animation.playing;
  event.target.textContent = animation.playing ? "Pause packets" : "Play packets";
  restartAnimation();
});

document.getElementById("compareButton").addEventListener("click", async () => {
  window.fifoSummary = (await loadFifoData())?.summary || null;
  if (window.currentSummary) renderComparison(window.currentSummary, window.fifoSummary);
});

document.getElementById("runButton").addEventListener("click", async () => {
  const button = document.getElementById("runButton");
  const status = document.getElementById("runStatus");
  button.disabled = true;
  status.textContent = "Running simulation...";
  try {
    const data = await runExperiment();
    window.currentSummary = data.summary;
    renderDashboard(data);
    status.textContent = `Updated at ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

Promise.all([loadData(), loadFifoData()])
  .then(([data, fifoData]) => {
    window.currentSummary = data.summary;
    window.fifoSummary = fifoData?.summary || null;
    renderDashboard(data, fifoData);
  })
  .catch((error) => {
    document.body.innerHTML = `<main><section class="panel"><h1>${error.message}</h1></section></main>`;
  });

const btnDockerStart = document.getElementById("btnDockerStart");
const btnDockerStop = document.getElementById("btnDockerStop");
const btnSensorStart = document.getElementById("btnSensorStart");
const sensorTerminal = document.getElementById("sensorTerminal");
let sensorEventSource = null;

if (btnDockerStart) {
  btnDockerStart.addEventListener("click", () => {
    btnDockerStart.textContent = "Starting...";
    fetch("/api/docker/start")
      .then(res => res.json())
      .then(data => {
        if (!data.ok) {
          btnDockerStart.textContent = "Start Docker Emulation";
          alert("Docker failed to start. Is Docker Desktop running?\n\nError: " + data.output);
        } else {
          btnDockerStart.textContent = "Docker Running";
        }
      });
  });
}

if (btnDockerStop) {
  btnDockerStop.addEventListener("click", () => {
    btnDockerStop.textContent = "Stopping...";
    fetch("/api/docker/stop")
      .then(res => res.json())
      .then(data => {
        btnDockerStart.textContent = "Start Docker Emulation";
        btnDockerStop.textContent = "Stop Docker";
      });
  });
}

if (btnSensorStart) {
  btnSensorStart.addEventListener("click", () => {
    if (sensorEventSource) {
      sensorEventSource.close();
      sensorEventSource = null;
      btnSensorStart.textContent = "Start Live Sensor Stream";
      sensorTerminal.innerHTML += `<div class="term-line" style="color: #778390;">> Stream stopped.</div>`;
      return;
    }
    btnSensorStart.textContent = "Stop Sensor Stream";
    sensorTerminal.innerHTML = `<div class="term-line" style="color: #778390;">> Connecting to broker...</div>`;
    sensorEventSource = new EventSource("/api/sensors/stream");
    sensorEventSource.onmessage = (e) => {
      const div = document.createElement("div");
      div.className = "term-line";
      div.textContent = e.data;
      if (e.data.includes("CRITICAL") || e.data.includes("[ERR]")) {
         div.style.color = "#fb7185";
      } else if (e.data.includes("NORMAL")) {
         div.style.color = "#38bdf8";
      }
      sensorTerminal.appendChild(div);
      sensorTerminal.scrollTop = sensorTerminal.scrollHeight;
    };
    sensorEventSource.onerror = () => {
      sensorEventSource.close();
      sensorEventSource = null;
      btnSensorStart.textContent = "Start Live Sensor Stream";
      sensorTerminal.innerHTML += `<div class="term-line" style="color: #fb7185;">> Error connecting to stream. Is server running?</div>`;
    };
  });
}
