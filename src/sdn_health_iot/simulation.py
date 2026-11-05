from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Dict, Iterable, List

from .controller import SDNController
from .models import DeviceProfile, Packet, QOS_TARGETS, Topology, TrafficClass


DEVICE_PROFILES = [
    DeviceProfile("code-blue-alarm", TrafficClass.EMERGENCY, 15.0, 1.0, 0.50),
    DeviceProfile("ecg-monitor", TrafficClass.CRITICAL, 11.0, 2.0, 0.35),
    DeviceProfile("spo2-sensor", TrafficClass.CRITICAL, 9.0, 1.5, 0.30),
    DeviceProfile("infusion-pump", TrafficClass.CRITICAL, 4.0, 2.5, 0.45),
    DeviceProfile("bp-monitor", TrafficClass.CLINICAL, 5.0, 2.0, 0.25),
    DeviceProfile("glucose-meter", TrafficClass.CLINICAL, 3.0, 1.4, 0.20),
    DeviceProfile("nurse-tablet", TrafficClass.CLINICAL, 4.5, 5.0, 0.40),
    DeviceProfile("bed-occupancy", TrafficClass.ROUTINE, 2.0, 1.0, 0.15),
    DeviceProfile("room-climate", TrafficClass.ROUTINE, 2.5, 1.1, 0.15),
    DeviceProfile("asset-tag", TrafficClass.ROUTINE, 6.0, 0.8, 0.25),
]

SOURCE_BY_CLASS = {
    TrafficClass.EMERGENCY: ["icu", "ward-a"],
    TrafficClass.CRITICAL: ["icu", "ward-a"],
    TrafficClass.CLINICAL: ["ward-a", "ward-b", "lab"],
    TrafficClass.ROUTINE: ["ward-a", "ward-b", "lab"],
}


@dataclass
class ClassMetrics:
    generated: int = 0
    delivered: int = 0
    deadline_misses: int = 0
    dropped: int = 0
    latencies: List[float] = None

    def __post_init__(self) -> None:
        if self.latencies is None:
            self.latencies = []

    def as_dict(self) -> Dict[str, float]:
        avg = statistics.mean(self.latencies) if self.latencies else 0.0
        jitter = statistics.pstdev(self.latencies) if len(self.latencies) > 1 else 0.0
        p95 = percentile(self.latencies, 95.0)
        loss_pct = 100.0 * (self.dropped + self.deadline_misses) / max(self.generated, 1)
        throughput = self.delivered / max(self.generated, 1)
        return {
            "generated": self.generated,
            "delivered": self.delivered,
            "dropped": self.dropped,
            "deadline_misses": self.deadline_misses,
            "avg_latency_ms": round(avg, 3),
            "p95_latency_ms": round(p95, 3),
            "jitter_ms": round(jitter, 3),
            "loss_pct": round(loss_pct, 3),
            "delivery_ratio": round(throughput, 4),
        }


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p / 100.0
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (idx - lower)


def poisson_sample(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 40:
        return max(0, int(rng.gauss(lam, lam ** 0.5)))
    threshold = pow(2.718281828459045, -lam)
    product = 1.0
    k = 0
    while product > threshold:
        k += 1
        product *= rng.random()
    return k - 1


def make_packet(profile: DeviceProfile, rng: random.Random, now_ms: float, load: float) -> Packet:
    source = rng.choice(SOURCE_BY_CLASS[profile.traffic_class])
    size = max(0.3, rng.gauss(profile.packet_size_kb, profile.packet_size_kb * profile.burstiness))
    deadline = QOS_TARGETS[profile.traffic_class]["latency_ms"]
    if rng.random() < profile.burstiness * min(load / 3.0, 1.0):
        size *= rng.uniform(1.4, 2.4)
    return Packet(
        created_ms=now_ms,
        size_kb=size,
        source=source,
        destination="ehr-server",
        traffic_class=profile.traffic_class,
        deadline_ms=deadline,
    )


def generate_packets(load: float, interval_ms: float, rng: random.Random, now_ms: float) -> Iterable[Packet]:
    for profile in DEVICE_PROFILES:
        lam = profile.packets_per_second * load * interval_ms / 1000.0
        for _ in range(poisson_sample(rng, lam)):
            yield make_packet(profile, rng, now_ms, load)


def run_single_load(load: float, policy: str, seed: int, duration_s: float = 24.0, step_ms: float = 25.0, use_rl: bool = False) -> Dict:
    rng = random.Random(seed)
    topology = Topology.hospital_fabric()
    controller = SDNController(topology, policy=policy)
    metrics = {cls: ClassMetrics() for cls in TrafficClass}
    path_counts: Dict[str, int] = {}
    steps = int(duration_s * 1000.0 / step_ms)

    if use_rl:
        from .rl_agent import RLAgent
        from .models import CLASS_WEIGHTS
        agent = RLAgent()

    for step in range(steps):
        # Simulate link failure halfway through the run for moderate/high loads
        if step == steps // 2 and load >= 0.7:
            try:
                failed_link = topology.link_between("edge-1", "core-1")
                failed_link.is_failed = True
            except KeyError:
                pass

        now_ms = step * step_ms
        packets = list(generate_packets(load, step_ms, rng, now_ms))
        if policy == "priority":
            packets.sort(key=lambda p: p.deadline_ms)
        for packet in packets:
            cls_metrics = metrics[packet.traffic_class]
            cls_metrics.generated += 1
            latency, ok, path = controller.transmit(packet)
            path_name = " > ".join(path) if path else "Dropped (No Path)"
            path_counts[path_name] = path_counts.get(path_name, 0) + 1
            if latency is None:
                cls_metrics.dropped += 1
            elif ok:
                cls_metrics.delivered += 1
                cls_metrics.latencies.append(latency)
            else:
                cls_metrics.deadline_misses += 1
                cls_metrics.latencies.append(latency)
        topology.drain(step_ms)

        if use_rl and step > 0 and step % (1000 // int(step_ms)) == 0:  # Update weights every 1 second
            current_metrics = {cls.value: metrics[cls].as_dict() for cls in TrafficClass}
            new_weights = agent.step(current_metrics, CLASS_WEIGHTS)
            CLASS_WEIGHTS.update(new_weights)

    class_results = {cls.value: metrics[cls].as_dict() for cls in TrafficClass}
    flow_rules = [
        {
            "source": source,
            "destination": destination,
            "class": cls,
            "path": path,
            "match": f"cookie=0x0, table=0, priority=100, ip,nw_src={source},nw_dst={destination}",
            "action": f"actions=set_queue:{'1' if policy == 'priority' else '0'},output:port_for_" + "->".join(path[1:]),
        }
        for (source, destination, cls), path in sorted(controller.flow_table.items())
    ]
    return {
        "load": round(load, 3),
        "policy": policy,
        "classes": class_results,
        "dominant_paths": sorted(path_counts.items(), key=lambda item: item[1], reverse=True)[:6],
        "flow_rules": flow_rules,
        "link_stats": topology.link_stats(),
    }
