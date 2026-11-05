from __future__ import annotations

import heapq
import json
import urllib.request
from typing import Dict, List, Optional, Tuple

from .models import Packet, Topology


class SDNController:
    """Path-selection logic that mimics SDN global network visibility."""

    def __init__(self, topology: Topology, policy: str = "priority") -> None:
        if policy not in {"priority", "fifo"}:
            raise ValueError("policy must be 'priority' or 'fifo'")
        self.topology = topology
        self.policy = policy
        self.flow_table: Dict[Tuple[str, str, str], List[str]] = {}

    def path_for(self, packet: Packet) -> List[str]:
        key = (packet.source, packet.destination, packet.traffic_class.value)
        path = self._shortest_dynamic_path(packet)
        self.flow_table[key] = path
        self._push_to_ryu(packet, path)
        return path

    def _push_to_ryu(self, packet: Packet, path: List[str]) -> None:
        if not path:
            return
        payload = {
            "dpid": 1,
            "cookie": 1,
            "table_id": 0,
            "priority": 100,
            "match": {"nw_src": packet.source, "nw_dst": packet.destination},
            "actions": [{"type": "OUTPUT", "port": 1}]
        }
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8081/stats/flowentry/add",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=0.05)
        except Exception:
            pass

    def _shortest_dynamic_path(self, packet: Packet) -> List[str]:
        start = packet.source
        end = packet.destination
        heap: List[Tuple[float, str, List[str]]] = [(0.0, start, [start])]
        best: Dict[str, float] = {start: 0.0}

        while heap:
            cost, node, path = heapq.heappop(heap)
            if node == end:
                return path
            if cost > best.get(node, float("inf")):
                continue
            for neighbor in self.topology.adjacency[node]:
                link = self.topology.link_between(node, neighbor)
                if link.is_failed:
                    continue
                next_cost = cost + link.projected_cost(packet.traffic_class, self.policy)
                if next_cost < best.get(neighbor, float("inf")):
                    best[neighbor] = next_cost
                    heapq.heappush(heap, (next_cost, neighbor, path + [neighbor]))

        # Instead of crashing, if no path is found (e.g. partition), return empty path
        return []

    def transmit(self, packet: Packet) -> Tuple[Optional[float], bool, List[str]]:
        path = self.path_for(packet)
        if not path:
            return None, False, []
        latency = 0.0
        for a, b in zip(path, path[1:]):
            link = self.topology.link_between(a, b)
            delay, accepted = link.transmit(packet, self.policy)
            if not accepted:
                return None, False, path
            latency += delay
        missed_deadline = latency > packet.deadline_ms
        return latency, not missed_deadline, path

