import numpy as np

class TabularQLearningScheduler:
    """
    Reinforcement Learning QoS scheduler dynamically optimizing priority queue weights
    for mission-critical healthcare IoT traffic streams.
    """
    def __init__(self, n_states: int = 10, n_actions: int = 4, alpha: float = 0.1, gamma: float = 0.95, epsilon: float = 0.1):
        self.q_table = np.zeros((n_states, n_actions))
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        # Actions: weight configurations [Class 0 weight, Class 1, Class 2, Class 3]
        self.action_weights = [
            [0.55, 0.25, 0.15, 0.05], # Ultra-critical emergency mode
            [0.45, 0.30, 0.15, 0.10], # High-priority clinical mode
            [0.35, 0.35, 0.20, 0.10], # Balanced patient ward mode
            [0.30, 0.30, 0.25, 0.15]  # Nominal background mode
        ]

    def select_action(self, state: int) -> int:
        if np.random.rand() < self.epsilon:
            return np.random.randint(len(self.action_weights))
        return int(np.argmax(self.q_table[state]))

    def update(self, state: int, action: int, reward: float, next_state: int):
        best_next_q = np.max(self.q_table[next_state])
        current_q = self.q_table[state, action]
        self.q_table[state, action] = current_q + self.alpha * (reward + self.gamma * best_next_q - current_q)
