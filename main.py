"""
Main CLI entry point for Priority-Aware SDN in Healthcare IoT Systems
Publication: 6th IEEE ICUIS 2026, Coimbatore
Simulates Priority vs FIFO scheduling across varying traffic loads and evaluates stability thresholds.
"""

import sys
import json
from src.sdn_health_iot.simulation import run_single_load

def format_class_summary(res: dict):
    for c_name, c_data in res["classes"].items():
        print(f"    - {c_name.capitalize():<12} : Latency={c_data['avg_latency_ms']:.2f} ms | P95={c_data['p95_latency_ms']:.2f} ms | Jitter={c_data['jitter_ms']:.2f} ms | Delivery={c_data['delivery_ratio']*100:.1f}%")

def main():
    print("=" * 76)
    print("  PRIORITY-AWARE SDN FOR HEALTHCARE IOT: STABILITY THRESHOLD ANALYSIS")
    print("  Venue: 6th IEEE International Conference on Ubiquitous Computing (ICUIS 2026)")
    print("=" * 76)

    loads = [0.5, 0.8, 1.2]

    print("\n[Phase 1] Simulating Priority-Aware Dynamic Queue Scheduling (QoS Mode)...")
    for load in loads:
        print(f"\n  --- Offered Network Traffic Load: {int(load*100)}% ---")
        res = run_single_load(load, policy="priority", seed=42, duration_s=10.0, use_rl=True)
        format_class_summary(res)

    print("\n[Phase 2] Simulating Conventional Best-Effort FIFO Baseline...")
    for load in loads:
        print(f"\n  --- Offered Network Traffic Load: {int(load*100)}% ---")
        res = run_single_load(load, policy="fifo", seed=42, duration_s=10.0, use_rl=False)
        format_class_summary(res)

    print("\n" + "=" * 76)
    print("  EMPIRICAL LATENCY & JITTER IMPROVEMENTS (From Published Paper)")
    print("=" * 76)
    print("  • P95 Latency Reduction for Critical ECG (Class 0) : -40.2% Reduction")
    print("  • Packet Jitter Suppression Under Heavy Congestion  : -84.1% Reduction")
    print("  • Guaranteed Packet Delivery for Intensive Alarms   : 100.0% Delivery")
    print("=" * 76)
    print("  AVAILABLE SYSTEM TOOLS:")
    print("  - run_experiment.sh : Automated sweep across baseline & stress scenarios")
    print("  - dashboard/        : Real-time Node.js + WebSocket telemetry dashboard")
    print("  - results/          : Publication SVG plots (loss, latency, stability)")
    print("=" * 76)

if __name__ == "__main__":
    main()
