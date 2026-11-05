import random
from typing import Dict, List

from .models import TrafficClass, QOS_TARGETS

class RLAgent:
    """
    A simple Tabular Q-Learning Agent that dynamically adjusts queue weights
    to maximize the number of packets meeting QoS targets.
    """
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.1):
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        # State: tuple of 4 booleans (emergency_ok, critical_ok, clinical_ok, routine_ok)
        # Action: 0: No change, 1: +Emergency, 2: +Critical, 3: +Clinical, 4: +Routine
        self.q_table: Dict[tuple, List[float]] = {}
        self.last_state = None
        self.last_action = None

    def get_state(self, metrics: Dict[str, Dict[str, float]]) -> tuple:
        state = []
        for cls in [TrafficClass.EMERGENCY, TrafficClass.CRITICAL, TrafficClass.CLINICAL, TrafficClass.ROUTINE]:
            cls_data = metrics.get(cls.value, {})
            target = QOS_TARGETS[cls]
            # Consider "ok" if latency is within target and loss is 0
            if cls_data:
                is_ok = (cls_data.get("p95_latency_ms", 0) <= target["latency_ms"] and
                         cls_data.get("dropped", 0) == 0)
            else:
                is_ok = True
            state.append(is_ok)
        return tuple(state)

    def calculate_reward(self, metrics: Dict[str, Dict[str, float]]) -> float:
        # Reward is the sum of delivery ratios
        reward = 0.0
        for cls_name, cls_data in metrics.items():
            reward += cls_data.get("delivery_ratio", 0.0)
        return reward

    def choose_action(self, state: tuple) -> int:
        if state not in self.q_table:
            self.q_table[state] = [0.0] * 5

        if random.random() < self.epsilon:
            return random.randint(0, 4)  # Explore
        else:
            return self.q_table[state].index(max(self.q_table[state]))  # Exploit

    def step(self, metrics: Dict[str, Dict[str, float]], current_weights: Dict[TrafficClass, int]) -> Dict[TrafficClass, int]:
        current_state = self.get_state(metrics)
        reward = self.calculate_reward(metrics)

        # Update Q-table if we have a previous state
        if self.last_state is not None and self.last_action is not None:
            if current_state not in self.q_table:
                self.q_table[current_state] = [0.0] * 5
                
            old_q = self.q_table[self.last_state][self.last_action]
            next_max = max(self.q_table[current_state])
            
            # Q-learning formula
            new_q = (1 - self.alpha) * old_q + self.alpha * (reward + self.gamma * next_max)
            self.q_table[self.last_state][self.last_action] = new_q

        # Choose next action
        action = self.choose_action(current_state)
        self.last_state = current_state
        self.last_action = action

        # Apply action to weights
        new_weights = current_weights.copy()
        if action == 1:
            new_weights[TrafficClass.EMERGENCY] += 1
        elif action == 2:
            new_weights[TrafficClass.CRITICAL] += 1
        elif action == 3:
            new_weights[TrafficClass.CLINICAL] += 1
        elif action == 4:
            new_weights[TrafficClass.ROUTINE] += 1

        # Keep weights from spiraling out of control (normalize implicitly by bounding)
        for cls, w in new_weights.items():
            new_weights[cls] = min(max(w, 1), 30)

        return new_weights
