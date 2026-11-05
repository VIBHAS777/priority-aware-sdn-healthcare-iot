from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import QOS_TARGETS, TrafficClass


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"


def scenario_loads(scenario: str) -> List[float]:
    if scenario == "stress":
        return [round(0.5 + i * 0.25, 2) for i in range(19)]
    return [round(0.5 + i * 0.2, 2) for i in range(16)]


def find_stability_threshold(rows: List[Dict], required_consecutive: int = 2) -> Optional[float]:
    violations = 0
    for row in rows:
        unstable = False
        for cls_name in ["emergency", "critical"]:
            metrics = row["classes"].get(cls_name)
            if not metrics:
                continue
            target = QOS_TARGETS[TrafficClass(cls_name)]
            if (
                metrics["p95_latency_ms"] > target["latency_ms"]
                or metrics["dropped"] > 0
                or metrics["jitter_ms"] > target["jitter_ms"] * 1.6
            ):
                unstable = True
        
        violations = violations + 1 if unstable else 0
        if violations >= required_consecutive:
            return row["load"]
    return None


def degradation_index(row: Dict) -> float:
    score = 0.0
    weights = {"emergency": 0.45, "critical": 0.35, "clinical": 0.15, "routine": 0.05}
    for cls_name, metrics in row["classes"].items():
        cls = TrafficClass(cls_name)
        target = QOS_TARGETS[cls]
        latency_ratio = metrics["p95_latency_ms"] / target["latency_ms"]
        loss_ratio = metrics["loss_pct"] / target["loss_pct"]
        score += weights.get(cls_name, 0.0) * max(latency_ratio, loss_ratio)
    return round(score, 3)


def write_artifacts(rows: List[Dict], scenario: str, policy: str, tag: str) -> Dict:
    DATA_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    threshold = find_stability_threshold(rows)
    summary = {
        "title": "Stability Threshold and Performance Degradation Analysis of Priority-Aware SDN in Healthcare IoT Systems",
        "scenario": scenario,
        "policy": policy,
        "stability_threshold_load": threshold,
        "loads_tested": [row["load"] for row in rows],
        "degradation": [{"load": row["load"], "index": degradation_index(row)} for row in rows],
        "final_load_metrics": rows[-1]["classes"],
        "dominant_paths_at_final_load": rows[-1]["dominant_paths"],
        "hot_links_at_final_load": rows[-1].get("link_stats", [])[:5],
        "flow_rules_at_final_load": rows[-1].get("flow_rules", []),
    }
    
    try:
        from .models import CLASS_WEIGHTS
        summary["final_class_weights"] = {cls.value: weight for cls, weight in CLASS_WEIGHTS.items()}
    except ImportError:
        pass

    suffix = "" if tag == "latest" else f"_{tag}"
    summary_path = DATA_DIR / f"latest_summary{suffix}.json"
    csv_path = DATA_DIR / f"latest_timeseries{suffix}.csv"
    summary_path.write_text(json.dumps({"summary": summary, "runs": rows}, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)
    write_flow_table(DATA_DIR / f"latest_flow_table{suffix}.json", rows[-1].get("flow_rules", []))
    write_svg_plots(rows, threshold)
    return summary


def write_csv(path: Path, rows: List[Dict]) -> None:
    fieldnames = [
        "load",
        "policy",
        "class",
        "generated",
        "delivered",
        "dropped",
        "deadline_misses",
        "avg_latency_ms",
        "p95_latency_ms",
        "jitter_ms",
        "loss_pct",
        "delivery_ratio",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            for cls, metrics in row["classes"].items():
                writer.writerow({"load": row["load"], "policy": row["policy"], "class": cls, **metrics})


def write_flow_table(path: Path, flow_rules: List[Dict]) -> None:
    path.write_text(json.dumps({"flow_rules": flow_rules}, indent=2), encoding="utf-8")


def write_svg_plots(rows: List[Dict], threshold: Optional[float]) -> None:
    render_line_chart(
        RESULTS_DIR / "latency_degradation.svg",
        "P95 Latency Degradation",
        rows,
        lambda row, cls: row["classes"][cls]["p95_latency_ms"],
        "P95 latency (ms)",
        threshold,
    )
    render_line_chart(
        RESULTS_DIR / "loss_degradation.svg",
        "Packet Loss and Deadline Miss Rate",
        rows,
        lambda row, cls: row["classes"][cls]["loss_pct"],
        "Loss (%)",
        threshold,
    )
    render_threshold_chart(RESULTS_DIR / "stability_threshold.svg", rows, threshold)


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2.0
    return dst_min + (value - src_min) * (dst_max - dst_min) / (src_max - src_min)


def render_line_chart(path: Path, title: str, rows: List[Dict], metric, y_label: str, threshold: Optional[float]) -> None:
    width, height = 920, 480
    margin = 64
    classes = ["emergency", "critical", "clinical", "routine"]
    colors = {"emergency": "#e11d48", "critical": "#ea580c", "clinical": "#06b6d4", "routine": "#22c55e"}
    loads = [row["load"] for row in rows]
    values = [metric(row, cls) for row in rows for cls in classes]
    y_max = max(values + [1.0]) * 1.15

    parts = [svg_header(width, height), f'<text x="32" y="38" class="title">{title}</text>']
    parts.append(axis(margin, width, height, y_label))
    for cls in classes:
        points = []
        for row in rows:
            x = scale(row["load"], min(loads), max(loads), margin, width - margin)
            y = scale(metric(row, cls), 0, y_max, height - margin, margin)
            points.append(f"{x:.1f},{y:.1f}")
        parts.append(f'<polyline class="line" stroke="{colors[cls]}" points="{" ".join(points)}"/>')
        parts.append(f'<text x="{width - margin + 8}" y="{scale(metric(rows[-1], cls), 0, y_max, height - margin, margin):.1f}" class="label">{cls}</text>')

    if threshold is not None:
        x = scale(threshold, min(loads), max(loads), margin, width - margin)
        parts.append(f'<line x1="{x:.1f}" y1="{margin}" x2="{x:.1f}" y2="{height - margin}" class="threshold"/>')
        parts.append(f'<text x="{x + 8:.1f}" y="{margin + 18}" class="label">stability threshold {threshold}x</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def render_threshold_chart(path: Path, rows: List[Dict], threshold: Optional[float]) -> None:
    width, height = 920, 360
    margin = 64
    loads = [row["load"] for row in rows]
    values = [degradation_index(row) for row in rows]
    y_max = max(values + [1.0]) * 1.1
    points = [
        f'{scale(row["load"], min(loads), max(loads), margin, width - margin):.1f},{scale(degradation_index(row), 0, y_max, height - margin, margin):.1f}'
        for row in rows
    ]
    parts = [
        svg_header(width, height),
        '<text x="32" y="38" class="title">Weighted Performance Degradation Index</text>',
        axis(margin, width, height, "degradation index"),
        f'<polyline class="line" stroke="#7a3db8" points="{" ".join(points)}"/>',
    ]
    if threshold is not None:
        x = scale(threshold, min(loads), max(loads), margin, width - margin)
        parts.append(f'<line x1="{x:.1f}" y1="{margin}" x2="{x:.1f}" y2="{height - margin}" class="threshold"/>')
        parts.append(f'<text x="{x + 8:.1f}" y="{height - margin - 10}" class="label">unstable from {threshold}x load</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def svg_header(width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
svg {{ background: #fbfcfd; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.title {{ font-size: 22px; font-weight: 700; fill: #1b2733; }}
.axis {{ stroke: #778390; stroke-width: 1.2; }}
.grid {{ stroke: #d8dee6; stroke-width: 0.8; }}
.line {{ fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
.threshold {{ stroke: #111827; stroke-width: 2; stroke-dasharray: 7 5; }}
.label {{ font-size: 13px; fill: #344054; }}
</style>'''


def axis(margin: int, width: int, height: int, y_label: str) -> str:
    return "\n".join(
        [
            f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" class="axis"/>',
            f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" class="axis"/>',
            f'<text x="{width / 2 - 36}" y="{height - 18}" class="label">offered load multiplier</text>',
            f'<text x="18" y="{height / 2}" class="label" transform="rotate(-90 18 {height / 2})">{y_label}</text>',
            f'<line x1="{margin}" y1="{margin}" x2="{width - margin}" y2="{margin}" class="grid"/>',
            f'<line x1="{margin}" y1="{(height) / 2}" x2="{width - margin}" y2="{(height) / 2}" class="grid"/>',
        ]
    )
