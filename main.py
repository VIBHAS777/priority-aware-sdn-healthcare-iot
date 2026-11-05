import numpy as np
from src.q_learning import TabularQLearningScheduler
from src.network_sim import HealthcareSDNSimulator

def main():
    print("=" * 70)
    print("  Priority-Aware SDN for Healthcare IoT: Stability Thresholds")
    print("  Publication: 6th IEEE ICUIS 2026, Coimbatore")
    print("=" * 70)

    sim = HealthcareSDNSimulator()
    scheduler = TabularQLearningScheduler()

    print("[*] Evaluating QoS metrics across increasing network traffic loads:")
    print("    Traffic loads: 50% (Normal) -> 80% (High) -> 120% (Emergency Burst)\n")

    loads = [0.5, 0.8, 1.2]
    for load in loads:
        state = min(int(load * 8), 9)
        action = scheduler.select_action(state)
        weights = scheduler.action_weights[action]
        
        qos = sim.evaluate_qos(load, weights)
        print(f"--- Traffic Load: {int(load*100)}% (Active Weights: {[round(w,2) for w in weights]}) ---")
        for traffic_class, metrics in qos.items():
            print(f"  {traffic_class:<28}: P95 Latency = {metrics['latency_p95_ms']:>6.2f} ms | Jitter = {metrics['jitter_ms']:>5.2f} ms | Loss = {metrics['packet_loss_percent']:>4.1f}%")
        print()

    print("=" * 70)
    print("  EXPERIMENTAL BENCHMARK SUMMARY (From Published Paper)")
    print("=" * 70)
    print("  [+] P95 Latency for Critical ECG (Class 0) : -40.2% Reduction")
    print("  [+] Network Packet Jitter                  : -84.1% Reduction")
    print("  [+] On-Time Delivery Under Emergency Spikes: 100.0% Guaranteed")
    print("=" * 70)

if __name__ == "__main__":
    main()
