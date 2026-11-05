const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn, exec } = require("child_process");

const root = path.resolve(__dirname, "..");
const port = Number(process.env.PORT || 8080);
const host = process.env.HOST || "127.0.0.1";

const mime = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".svg": "image/svg+xml; charset=utf-8",
};

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function runExperiment(req, res) {
  const parsed = new URL(req.url, `http://${host}:${port}`);
  const scenario = parsed.searchParams.get("scenario") === "stress" ? "stress" : "baseline";
  const policy = parsed.searchParams.get("policy") === "fifo" ? "fifo" : "priority";
  const seed = String(Math.max(1, Math.min(9999, Number(parsed.searchParams.get("seed") || 7))));
  const duration = String(Math.max(5, Math.min(90, Number(parsed.searchParams.get("duration") || 16))));
  const use_rl = parsed.searchParams.get("use_rl") === "true";
  const args = [
    "-m",
    "src.sdn_health_iot",
    "--scenario",
    scenario,
    "--policy",
    policy,
    "--seed",
    seed,
    "--duration",
    duration,
  ];
  if (use_rl) args.push("--use-rl");

  const pythonPath = fs.existsSync("/opt/anaconda3/bin/python3") ? "/opt/anaconda3/bin/python3" : "python3";
  const child = spawn(pythonPath, args, { cwd: root });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });
  child.on("close", (code) => {
    if (code !== 0) {
      sendJson(res, 500, { ok: false, error: stderr || stdout || "Experiment failed." });
      return;
    }
    fs.readFile(path.join(root, "data", "latest_summary.json"), "utf8", (err, data) => {
      if (err) {
        sendJson(res, 500, { ok: false, error: "Experiment completed but summary file was not found." });
        return;
      }
      sendJson(res, 200, { ok: true, output: stdout, data: JSON.parse(data) });
    });
  });
}

function resolveRequest(url) {
  const clean = decodeURIComponent(url.split("?")[0]);
  if (clean === "/") return path.join(__dirname, "index.html");
  if (clean.startsWith("/data/")) return path.join(root, clean);
  if (clean.startsWith("/results/")) return path.join(root, clean);
  return path.join(__dirname, clean);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith("/api/run")) {
    runExperiment(req, res);
    return;
  }

  if (req.url.startsWith("/api/docker/start")) {
    exec("docker-compose up -d", { cwd: root }, (error, stdout, stderr) => {
      sendJson(res, error ? 500 : 200, { ok: !error, output: stdout || stderr });
    });
    return;
  }

  if (req.url.startsWith("/api/docker/stop")) {
    exec("docker-compose down", { cwd: root }, (error, stdout, stderr) => {
      sendJson(res, error ? 500 : 200, { ok: !error, output: stdout || stderr });
    });
    return;
  }

  if (req.url.startsWith("/api/sensors/stream")) {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive"
    });
    res.write("data: Connected to live sensor stream...\n\n");
    
    const pythonPath = fs.existsSync("/opt/anaconda3/bin/python3") ? "/opt/anaconda3/bin/python3" : "python3";
    const child = spawn(pythonPath, ["-u", "src/mqtt_publishers.py"], { cwd: root });
    
    child.stdout.on("data", (chunk) => {
      chunk.toString().split("\n").forEach(line => {
        if (line.trim()) res.write(`data: ${line}\n\n`);
      });
    });
    
    child.stderr.on("data", (chunk) => {
      chunk.toString().split("\n").forEach(line => {
        if (line.trim()) res.write(`data: [ERR] ${line}\n\n`);
      });
    });
    
    req.on("close", () => {
      child.kill();
    });
    return;
  }

  const filePath = resolveRequest(req.url);
  if (!filePath.startsWith(root)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("Not found. Run python3 -m src.sdn_health_iot first if data is missing.");
      return;
    }
    res.writeHead(200, { "Content-Type": mime[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(port, host, () => {
  console.log(`Healthcare IoT SDN dashboard running at http://localhost:${port}`);
});
