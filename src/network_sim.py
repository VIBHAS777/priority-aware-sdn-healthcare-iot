import numpy as np

class HealthcareSDNSimulator:
    """
    Simulates OpenFlow SDN topology with 4 priority queue classes:
      - Class 0: Emergency Telemetry (ECG, Defibrillator, SpO2 Alarm)
      - Class 1: Real-Time Patient Vitals (Heart Rate, Blood Pressure)
      - Class 2: Diagnostic Imaging & PACS Transmissions
      - Class 3: General EHR & Administrative Telemetry
    """
    def __init__(self):
        self.class_names = [
            "Class 0 (Emergency ECG)",
            "Class 1 (Real-Time Vitals)",
            "Class 2 (Diagnostic Imaging)",
            "Class 3 (General EHR Data)"
        ]

    def evaluate_qos(self, load_factor: float, weights: list) -> dict:
        """
        Calculates P95 latency, jitter, and packet loss rate under specified network load.
        """
        # Baseline latency without priority scheduling increases exponentially with load
        base_latency = 12.0 * np.exp(1.8 * load_factor)
        
        results = {}
        for c_idx in range(4):
            w = weights[c_idx]
            # Higher priority weight suppresses queue buffering
            c_latency = max(2.5, base_latency * (0.25 / w) * (0.6 + 0.1 * c_idx))
            c_jitter = c_latency * 0.15 * (1.0 - w)
            # Packet loss occurs if buffer overflows under extreme load
            overflow_prob = max(0.0, (load_factor - (w * 1.5)) * 0.08)
            
            results[self.class_names[c_idx]] = {
                "latency_p95_ms": round(c_latency, 2),
                "jitter_ms": round(c_jitter, 2),
                "packet_loss_percent": round(overflow_prob * 100, 2)
            }
        return results
