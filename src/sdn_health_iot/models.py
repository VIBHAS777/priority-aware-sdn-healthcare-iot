from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class TrafficClass(str, Enum):
    EMERGENCY = "emergency"
    CRITICAL = "critical"
    CLINICAL = "clinical"
    ROUTINE = "routine"


QOS_TARGETS = {
    TrafficClass.EMERGENCY: {"latency_ms": 30.0, "loss_pct": 0.1, "jitter_ms": 10.0},
    TrafficClass.CRITICAL: {"latency_ms": 80.0, "loss_pct": 1.0, "jitter_ms": 25.0},
    TrafficClass.CLINICAL: {"latency_ms": 150.0, "loss_pct": 3.0, "jitter_ms": 55.0},
    TrafficClass.ROUTINE: {"latency_ms": 300.0, "loss_pct": 8.0, "jitter_ms": 120.0},
}


CLASS_WEIGHTS = {
    TrafficClass.EMERGENCY: 10,
    TrafficClass.CRITICAL: 5,
    TrafficClass.CLINICAL: 3,
    TrafficClass.ROUTINE: 1,
}


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    traffic_class: TrafficClass
    packets_per_second: float
    packet_size_kb: float
    burstiness: float


@dataclass(frozen=True)
class Packet:
    created_ms: float
    size_kb: float
    source: str
    destination: str
    traffic_class: TrafficClass
    deadline_ms: float


@dataclass
class Link:
    a: str
    b: str
    capacity_kbps: float
    propagation_ms: float
    queue_limit_kb: float
    queues: Dict[TrafficClass, float] = field(default_factory=lambda: {c: 0.0 for c in TrafficClass})
    max_queue_kb: float = 0.0
    transmitted_kb: float = 0.0
    dropped_packets: int = 0
    drops_by_class: Dict[TrafficClass, int] = field(default_factory=lambda: {c: 0 for c in TrafficClass})
    is_failed: bool = False

    def key(self) -> Tuple[str, str]:
        return tuple(sorted((self.a, self.b)))

    def utilization(self) -> float:
        return min(1.0, sum(self.queues.values()) / max(self.queue_limit_kb, 1.0))

    def projected_cost(self, traffic_class: TrafficClass, policy: str) -> float:
        queue_kb = sum(self.queues.values())
        if policy == "priority":
            queue_kb = self.queues[traffic_class] + 0.35 * sum(
                kb for cls, kb in self.queues.items() if CLASS_WEIGHTS[cls] < CLASS_WEIGHTS[traffic_class]
            )
        service_ms = 1000.0 * queue_kb / max(self.capacity_kbps, 1.0)
        return self.propagation_ms + service_ms + 18.0 * self.utilization()

    def transmit(self, packet: Packet, policy: str) -> Tuple[float, bool]:
        if self.is_failed:
            self.dropped_packets += 1
            self.drops_by_class[packet.traffic_class] += 1
            return 0.0, False

        total_queue = sum(self.queues.values())
        if total_queue + packet.size_kb > self.queue_limit_kb:
            self.dropped_packets += 1
            self.drops_by_class[packet.traffic_class] += 1
            return 0.0, False

        effective_queue = total_queue
        if policy == "priority":
            higher_or_equal = [
                kb for cls, kb in self.queues.items() if CLASS_WEIGHTS[cls] >= CLASS_WEIGHTS[packet.traffic_class]
            ]
            lower = [
                kb for cls, kb in self.queues.items() if CLASS_WEIGHTS[cls] < CLASS_WEIGHTS[packet.traffic_class]
            ]
            effective_queue = sum(higher_or_equal) + 0.25 * sum(lower)

        self.queues[packet.traffic_class] += packet.size_kb
        self.transmitted_kb += packet.size_kb
        self.max_queue_kb = max(self.max_queue_kb, sum(self.queues.values()))
        queue_delay_ms = 1000.0 * effective_queue / max(self.capacity_kbps, 1.0)
        tx_delay_ms = 1000.0 * packet.size_kb / max(self.capacity_kbps, 1.0)
        return self.propagation_ms + queue_delay_ms + tx_delay_ms, True

    def drain(self, interval_ms: float) -> None:
        budget = self.capacity_kbps * interval_ms / 1000.0
        for cls in sorted(TrafficClass, key=lambda c: CLASS_WEIGHTS[c], reverse=True):
            take = min(self.queues[cls], budget)
            self.queues[cls] -= take
            budget -= take
            if budget <= 0:
                break


@dataclass
class Topology:
    nodes: List[str]
    links: Dict[Tuple[str, str], Link]
    adjacency: Dict[str, List[str]]

    @classmethod
    def hospital_fabric(cls) -> "Topology":
        raw_links = [
            ("ward-a", "edge-1", 180.0, 3.0, 130.0),
            ("ward-b", "edge-1", 170.0, 4.0, 125.0),
            ("icu", "edge-2", 220.0, 2.0, 150.0),
            ("lab", "edge-2", 150.0, 5.0, 110.0),
            ("edge-1", "core-1", 300.0, 4.0, 220.0),
            ("edge-2", "core-1", 320.0, 3.0, 240.0),
            ("edge-1", "core-2", 210.0, 6.0, 160.0),
            ("edge-2", "core-2", 220.0, 6.0, 160.0),
            ("core-1", "controller", 500.0, 2.0, 300.0),
            ("core-2", "controller", 420.0, 3.0, 280.0),
            ("core-1", "ehr-server", 440.0, 2.0, 260.0),
            ("core-2", "ehr-server", 360.0, 4.0, 220.0),
        ]
        links: Dict[Tuple[str, str], Link] = {}
        adjacency: Dict[str, List[str]] = {}
        nodes = set()
        for a, b, capacity, propagation, queue_limit in raw_links:
            nodes.update([a, b])
            link = Link(a, b, capacity, propagation, queue_limit)
            links[link.key()] = link
            adjacency.setdefault(a, []).append(b)
            adjacency.setdefault(b, []).append(a)
        return cls(sorted(nodes), links, adjacency)

    def link_between(self, a: str, b: str) -> Link:
        return self.links[tuple(sorted((a, b)))]

    def drain(self, interval_ms: float) -> None:
        for link in self.links.values():
            link.drain(interval_ms)

    def link_stats(self) -> List[Dict[str, object]]:
        stats = []
        for link in self.links.values():
            peak_utilization = min(1.0, link.max_queue_kb / max(link.queue_limit_kb, 1.0))
            stats.append(
                {
                    "a": link.a,
                    "b": link.b,
                    "capacity_kbps": link.capacity_kbps,
                    "propagation_ms": link.propagation_ms,
                    "queue_limit_kb": link.queue_limit_kb,
                    "peak_queue_kb": round(link.max_queue_kb, 3),
                    "peak_utilization": round(peak_utilization, 4),
                    "transmitted_kb": round(link.transmitted_kb, 3),
                    "dropped_packets": link.dropped_packets,
                    "drops_by_class": {cls.value: count for cls, count in link.drops_by_class.items()},
                    "is_failed": link.is_failed,
                }
            )
        return sorted(stats, key=lambda item: item["peak_utilization"], reverse=True)
