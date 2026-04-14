import random
import numpy as np

class ReplayBuffer:
    def __init__(self, capacity=10000, batch_size=32, n_step=5, discount=0.99):
        self.capacity = capacity
        self.batch_size = batch_size
        self.n_step = n_step
        self.discount = discount
        self.buffer = []
        
    def save_trajectory(self, trajectory):
        # trajectory is a list of (o_t, a_t, p_t, v_t, u_t)
        # compute n-step value targets
        n_step_traj = []
        for i in range(len(trajectory)):
            o_t, a_t, p_t, v_t, u_t = trajectory[i]
            
            # Compute N-step return
            target_value = 0
            for j in range(self.n_step):
                if i + j < len(trajectory):
                    target_value += (self.discount ** j) * trajectory[i+j][4] # reward u_t is at index 4
                else:
                    break
            if i + self.n_step < len(trajectory):
                target_value += (self.discount ** self.n_step) * trajectory[i + self.n_step][3] # bootstrap value
            
            n_step_traj.append((o_t, a_t, p_t, target_value, u_t))
            
        self.buffer.append(n_step_traj)
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)
            
    def sample(self, k_steps):
        # Sample sequences for unrolling
        batch = []
        for _ in range(self.batch_size):
            traj = random.choice(self.buffer)
            start_index = random.randint(0, max(0, len(traj) - k_steps - 1))
            
            sequence = traj[start_index : start_index + k_steps + 1]
            
            # pad if sequence is too short
            while len(sequence) < k_steps + 1:
                sequence.append((
                    np.zeros_like(traj[0][0]), # obs
                    0,                         # action
                    np.ones_like(traj[0][2]) / len(traj[0][2]), # policy
                    0.0,                       # value
                    0.0                        # reward
                ))
            batch.append(sequence)
        
        # transpose batch to have [k_steps, batch_size, ...]
        batch_transposed = list(zip(*batch))
        return batch_transposed

    def __len__(self):
        return len(self.buffer)
