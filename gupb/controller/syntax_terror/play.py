import torch

from gupb.controller.syntax_terror.syntax_terror import SyntaxTerror
from gupb.controller.syntax_terror.network import MuZeroNetwork
from gupb.controller.random import RandomController
from gupb.runner import Runner


def play_muzero(model_path):
    print(f"Loading MuZero model from {model_path}...")

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available() else "cpu"
    )
    print(f"Using device: {device}")

    state_dict = torch.load(model_path, map_location=device)

    # Infer hidden_channels purely from state_dict shape to be robust to MVP vs Full models
    hidden_channels = state_dict["representation.conv.weight"].shape[0]

    network = MuZeroNetwork(hidden_channels=hidden_channels)
    network.load_state_dict(state_dict)
    network.to(device)
    network.eval()

    mu_controller = SyntaxTerror("TrainedMuZero", network=network, is_training=False)

    random_controllers = [RandomController(f"RandomBot{i}") for i in range(1, 4)]

    config = {
        "arenas": ["ordinary_chaos"],
        "controllers": [mu_controller] + random_controllers,
        "start_balancing": False,
        "visualise": True,
        "show_sight": mu_controller,
        "runs_no": 5,
        "profiling_metrics": [],
    }

    print("Starting 5 games on arena 'ordinary_chaos' against Random Bots...")
    runner = Runner(config)
    runner.run()
    runner.print_scores()


if __name__ == "__main__":
    import click

    @click.command()
    @click.argument("model_path", type=click.Path(exists=True))
    def main(model_path):
        play_muzero(model_path)

    main()
