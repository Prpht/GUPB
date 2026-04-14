import logging
import os
import time
import importlib

import numpy as np
import ray
import torch
import torch.nn.functional as F
import torch.optim as optim

from gupb.controller.syntax_terror.syntax_terror import SyntaxTerror
from gupb.controller.syntax_terror.network import MuZeroNetwork
from gupb.controller.syntax_terror.replay_buffer import ReplayBuffer
from gupb.runner import Runner


HASH = hash(time.time()) % 1000


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    else:
        return torch.device("cpu")


@ray.remote
class SelfPlayWorker:
    def __init__(self, runner_config=None, rewards_config=None):
        self.runner_config = runner_config
        self.rewards_config = rewards_config
        gm_log_file = f"/net/people/plgrid/plgmarcin001/projects/GUPB/logs/t_games_muzero_{HASH}.log"
        # logging.basicConfig(
        #     level=logging.INFO,
        #     format="%(asctime)s - %(levelname)s - %(message)s",
        #     handlers=[logging.FileHandler(gm_log_file)],
        # )

    def play_game(self, network_weights, is_mvp=False):
        game_start = time.time()
        device = get_device()
        network = MuZeroNetwork(input_channels=8, hidden_channels=16 if is_mvp else 32)
        if is_mvp and network_weights:
            # For MVP it might just be cpu to avoid OOM
            device = torch.device("cpu")

        if network_weights:
            network.load_state_dict(network_weights)
        network.to(device)
        network.eval()

        # Override config controllers with our bot
        if self.rewards_config:
            controller = SyntaxTerror(
                "MuZeroTrainer",
                network=network,
                is_training=True,
                rewards_scaling=self.rewards_config,
            )
        else:
            controller = SyntaxTerror(
                "MuZeroTrainer", network=network, is_training=True
            )
        # Use simpler search for MVP
        if is_mvp:
            controller.mcts.num_simulations = 2

        config = {
            "arenas": ["ordinary_chaos"],
            "controllers": [controller],
            "start_balancing": False,
            "visualise": False,
            "show_sight": None,
            "runs_no": 1 if is_mvp else 2,
            "profiling_metrics": [],
        }

        if self.runner_config:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "runner_config", self.runner_config
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "CONFIGURATION"):
                ext_config = module.CONFIGURATION.copy()
                if "controllers" in ext_config:
                    new_controllers = []
                    for c in ext_config["controllers"]:
                        new_controllers.append(c)
                    new_controllers.append(controller)
                    ext_config["controllers"] = new_controllers
                config.update(ext_config)

        runner = Runner(config)
        runner.run()

        controller_score = runner.scores[controller.name]
        best_score = max(runner.scores.values())
        if best_score > 0:
            controller.last_game_score = controller_score / best_score + (
                1.0 if controller_score == best_score else 0.0
            )
        else:
            controller.last_game_score = 0

        if hasattr(controller, "terminal_indices"):
            for idx in controller.terminal_indices:
                # Unpack the old tuple
                obs, act_idx, policy, value, old_u_t = controller.trajectory[idx]

                new_u_t = old_u_t + (
                    controller.last_game_score
                    * controller.rewards_scaling["final_score_multiplier"]
                )

                # Replace the tuple in the list
                controller.trajectory[idx] = (obs, act_idx, policy, value, new_u_t)

            controller.terminal_indices.clear()

        game_end = time.time()
        game_time = game_end - game_start
        # logging.info(
        #     f"Game took {game_time:.2f}s. Our score: {controller_score} out of {best_score}"
        # )

        return controller.trajectory


def train_muzero(mode="mvp", resume_from=None, runner_config=None, rewards_config=None):
    os.makedirs("models", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/training_muzero_{mode}_{HASH}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file)],
    )

    logging.info(f"Starting MuZero {HASH} training in {mode} mode...")

    # Initialize Ray
    if not ray.is_initialized():
        if mode == "mvp":
            ray.init(num_cpus=1, log_to_driver=False)
        else:
            ray.init(_temp_dir="/net/afscra/people/plgmarcin001/ray_temp")

    device = get_device()
    logging.info(f"Using device: {device}")

    if mode == "mvp":
        num_workers = 1
        num_iterations = 5
        games_per_iteration = 1
        k_steps = 2
        batch_size = 4
        replay_capacity = 100
        hidden_channels = 16
    else:
        num_workers = 9
        num_iterations = 2000
        games_per_iteration = 18
        k_steps = 5
        batch_size = 512
        replay_capacity = 10000
        hidden_channels = 32

    network = MuZeroNetwork(input_channels=8, hidden_channels=hidden_channels).to(
        device
    )
    optimizer = optim.Adam(network.parameters(), lr=1e-3, weight_decay=1e-4)
    buffer = ReplayBuffer(capacity=replay_capacity, batch_size=batch_size, n_step=5)

    if rewards_config:
        module = importlib.import_module(rewards_config)
        config = module.REWARDS_SCALING
        workers = [
            SelfPlayWorker.remote(runner_config=runner_config, rewards_config=config)
            for _ in range(num_workers)
        ]
        logging.info(f"Loaded rewards config: {config}")
    else:
        workers = [
            SelfPlayWorker.remote(runner_config=runner_config)
            for _ in range(num_workers)
        ]
        logging.info(f"Default rewards config")

    start_iteration = 0
    if resume_from:
        logging.info(f"Resuming from checkpoint: {resume_from}")
        checkpoint = torch.load(resume_from, map_location=device)

        if "model_state_dict" in checkpoint:
            network.load_state_dict(checkpoint["model_state_dict"])
            if "optimizer_state_dict" in checkpoint:
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_iteration = checkpoint.get("iteration", 0)
        else:
            network.load_state_dict(checkpoint)
            start_iteration = 0
            logging.info(
                "Loaded pure model weights instead of full checkpoint. Optimizer state reset."
            )

        logging.info(
            f"Running warm-up to repopulate Replay Buffer (target: {batch_size} trajectories)..."
        )
        network_weights = network.state_dict()
        network_weights_ref = ray.put({k: v.cpu() for k, v in network_weights.items()})

        games_played_in_warmup = 0
        while games_played_in_warmup < batch_size:
            futures = []
            for i in range(games_per_iteration):
                worker = workers[i % num_workers]
                futures.append(
                    worker.play_game.remote(network_weights_ref, is_mvp=(mode == "mvp"))
                )
            results = ray.get(futures)
            for trajectory in results:
                if trajectory:
                    buffer.save_trajectory(trajectory)
                    games_played_in_warmup += 1
            logging.info(
                f"Warm-up progress: {games_played_in_warmup}/{batch_size} trajectories collected"
            )

    for iteration in range(start_iteration, num_iterations):
        logging.info(f"--- Iteration {iteration + 1}/{num_iterations} ---")
        start_time = time.time()
        network_weights = network.state_dict()
        network_weights_ref = ray.put({k: v.cpu() for k, v in network_weights.items()})

        # Generate self-play games
        futures = []
        for i in range(games_per_iteration):
            worker = workers[i % num_workers]
            futures.append(
                worker.play_game.remote(network_weights_ref, is_mvp=(mode == "mvp"))
            )

        results = ray.get(futures)
        for trajectory in results:
            if trajectory:
                buffer.save_trajectory(trajectory)

        # Optimize
        if len(buffer) < batch_size:
            continue

        batch = buffer.sample(k_steps)
        # batch is transposed: [k_steps + 1, batch_size, ...]

        obs_batch, action_batch, policy_batch, value_batch, reward_batch = zip(
            *batch[0]
        )
        obs_tensor = torch.tensor(np.stack(obs_batch), dtype=torch.float32).to(device)

        # Initial inference
        hidden_state, policy_logits, value_pred = network.initial_inference(obs_tensor)

        # Calculate losses
        loss_p = 0
        loss_v = 0
        loss_r = 0
        loss_d = 0
        loss_c = 0

        # Initial losses (t=0)
        target_policy = torch.tensor(np.stack(policy_batch), dtype=torch.float32).to(
            device
        )
        target_value = (
            torch.tensor(value_batch, dtype=torch.float32).unsqueeze(1).to(device)
        )

        loss_p += -torch.sum(
            target_policy * F.log_softmax(policy_logits, dim=1), dim=1
        ).mean()
        loss_v += F.mse_loss(value_pred, target_value)

        # Decoding initial hidden state
        decoded_obs = network.decoder(hidden_state)
        # Assuming observation reconstruction MSE (could be BCE if channels are perfectly binary)
        loss_d += F.mse_loss(decoded_obs, obs_tensor)

        # Unroll dynamically
        for t in range(1, k_steps + 1):
            obs_batch, action_batch, policy_batch, value_batch, reward_batch = zip(
                *batch[t]
            )
            actions_tensor = torch.tensor(action_batch, dtype=torch.long).to(device)
            target_policy = torch.tensor(
                np.stack(policy_batch), dtype=torch.float32
            ).to(device)
            target_value = (
                torch.tensor(value_batch, dtype=torch.float32).unsqueeze(1).to(device)
            )
            target_reward = (
                torch.tensor(reward_batch, dtype=torch.float32).unsqueeze(1).to(device)
            )
            target_obs = torch.tensor(np.stack(obs_batch), dtype=torch.float32).to(
                device
            )

            # Recurrent inference
            hidden_state, reward_pred, policy_logits, value_pred = (
                network.recurrent_inference(hidden_state, actions_tensor)
            )

            # True representation of current state for consistency loss
            with torch.no_grad():
                true_hidden_state, _, _ = network.initial_inference(target_obs)

            loss_p += -torch.sum(
                target_policy * F.log_softmax(policy_logits, dim=1), dim=1
            ).mean()
            loss_v += F.mse_loss(value_pred, target_value)
            loss_r += F.mse_loss(reward_pred, target_reward)

            z, p = network.simsiam(hidden_state)
            z_true, p_true = network.simsiam(true_hidden_state)

            # Negative cosine similarity
            loss_c -= F.cosine_similarity(p, z_true.detach(), dim=1).mean()
            loss_c -= F.cosine_similarity(p_true, z.detach(), dim=1).mean()

        total_loss = loss_p + loss_v + loss_r + 25.0 * loss_d + 1.0 * loss_c

        optimizer.zero_grad()
        total_loss.backward()

        # Apply norm clipping to the whole network network
        torch.nn.utils.clip_grad_norm_(network.parameters(), max_norm=5.0)

        optimizer.step()

        end_time = time.time()
        time_elapsed = end_time - start_time

        logging.info(
            f"Iter took {time_elapsed}s\nLosses - P: {loss_p.item():.3f}, V: {loss_v.item():.3f}, R: {loss_r.item():.3f}, D: {loss_d.item():.3f}, C: {loss_c.item():.3f}, Total: {total_loss.item():.3f}"
        )

        if (iteration + 1) % 500 == 0:
            checkpoint_path = f"models/checkpoint_{HASH}_{iteration + 1}.pt"
            torch.save(
                {
                    "iteration": iteration + 1,
                    "model_state_dict": network.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                },
                checkpoint_path,
            )
            logging.info(f"Checkpoint saved to {checkpoint_path}")

    model_path = f"models/muzero_model_{HASH}_{mode}.pth"
    torch.save(network.state_dict(), model_path)
    logging.info(f"Training completed. Model saved to {model_path}")


if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--mode", type=click.Choice(["mvp", "full"]), default="mvp")
    @click.option(
        "--resume-from",
        type=str,
        default=None,
        help="Path to checkpoint to resume from (e.g., models/checkpoint_100.pt)",
    )
    @click.option(
        "--runner-config",
        type=str,
        default=None,
        help="Path to runner config python file (e.g., gupb/muzero_config_1.py)",
    )
    @click.option(
        "--rewards-config",
        type=str,
        default=None,
        help="Path to rewards config python file (e.g., gupb/muzero_config_1.py)",
    )
    def main(mode, resume_from, runner_config, rewards_config):
        train_muzero(mode, resume_from, runner_config, rewards_config)

    main()
