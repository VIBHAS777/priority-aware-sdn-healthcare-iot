# Stability Threshold and Performance Degradation Analysis of Priority-Aware SDN in Healthcare IoT Systems

[![Conference](https://img.shields.io/badge/Conference-6th_ICUIS_2026-blue.svg)](https://icuis.org/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![SDN](https://img.shields.io/badge/Architecture-OpenFlow_SDN-orange.svg)](https://opennetworking.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Presented at the **6th International Conference on Ubiquitous Computing and Intelligent Information Systems (ICUIS 2026)**, Coimbatore, India.

---

## 👥 Authors
- **A Vibhas Reddy** ([@VIBHAS777](https://github.com/VIBHAS777))
- **S Pavan Kumar**
- **Thangam S**

---

## 🏥 Overview
Critical hospital IoT environments transmit heterogeneous telemetry streams over shared network topologies—ranging from life-saving ICU patient monitors (ECG, blood pressure, oxygen saturation) to bulk medical imaging (PACS) and administrative Electronic Health Records (EHR). Under high traffic contention, best-effort queuing causes intolerable jitter and packet drops on vital telemetry.

This repository provides an OpenFlow-compatible **Software-Defined Networking (SDN)** framework integrated with **Tabular Q-Learning**. The controller dynamically modulates queue scheduling weights across four medical traffic priority classes, guaranteeing 100% on-time critical packet delivery with a **-40% reduction in P95 latency** and an **-84% reduction in transmission jitter**.

---

## 📁 Repository Structure
```
priority-aware-sdn-healthcare-iot/
├── paper/
│   ├── Stability_Threshold_and_Performance_Degradation_Priority_Aware_SDN.pdf
│   └── Certificate_ICUIS_2026.pdf
├── src/
│   ├── q_learning.py      # Tabular Q-learning priority weight adapter
│   └── network_sim.py     # 4-Class QoS queue & latency degradation engine
├── main.py                # Multi-load QoS evaluation benchmark
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 🚀 Quick Start
```bash
git clone https://github.com/VIBHAS777/priority-aware-sdn-healthcare-iot.git
cd priority-aware-sdn-healthcare-iot
python main.py
```

---

## 📜 Citation
```bibtex
@inproceedings{reddy2026sdnhealthcare,
  title={Stability Threshold and Performance Degradation Analysis of Priority-Aware SDN in Healthcare IoT Systems},
  author={Reddy, A Vibhas and Kumar, S Pavan and Thangam, S},
  booktitle={6th International Conference on Ubiquitous Computing and Intelligent Information Systems (ICUIS)},
  year={2026}
}
```
