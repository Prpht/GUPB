import torch
import torch.multiprocessing as mp
import random
import time
import os
import glob
import shutil
from gupb.model import games
from gupb.controller import random as random_controller
from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu
from gupb.controller.biwakspot import BiwakSpot
from gupb.controller.bigbot import BIGbot
from gupb.controller.bob import Bob
from gupb.controller.czak_noris import CzakNoris
from gupb.controller.jeffrey_e import JeffreyEController
from gupb.controller.karakin import KarakinController
from gupb.controller.syntax_terror import SyntaxTerror
from gupb.controller.the_trooper import TheTrooper
from gupb.controller.pudzian.pudzian import Pudzian

LEAGUE_DIR = os.path.join(
    os.path.dirname(__file__),
    "league"
)

os.makedirs(LEAGUE_DIR, exist_ok=True)

ARENAS = [
    "ordinary_chaos",
    "lone_sanctum",
    "isolated_shrine",
    "dungeon",
    # "wasteland",
    # "archipelago",
    # "mini",
    # "island",
    # "fisher_island",
]

AVAILABLE_BOTS = [
    BenjaminNetanyahu("BenjaminNetanyahu"),
    BiwakSpot("BiwakSpot"),
    BIGbot("BIGbot"),
    Bob("BobMinion"),
    CzakNoris("CzakNoris"),
    JeffreyEController("JeffreyE"),
    KarakinController("Karakin"),
    SyntaxTerror("SyntaxTerror"),
    TheTrooper("The Trooper"),
    random_controller.RandomController("Alice"),
    random_controller.RandomController("Bob"),
    random_controller.RandomController("Cecilia"),
    random_controller.RandomController("Darius"),
]

REQUIRED_BOTS = [
    BenjaminNetanyahu("BenjaminNetanyahu"),
    BiwakSpot("BiwakSpot"),
]


def save_snapshot(brain, tag):

    snapshot_path = os.path.join(
        LEAGUE_DIR,
        f"snapshot_{tag}.pt"
    )
    snapshots = sorted(get_league_models(), key=os.path.getmtime)
    if len(snapshots) > 10:
        os.remove(snapshots[0])
    brain.save()
    shutil.copy2(brain.model_path, snapshot_path)

    print(f"[LEAGUE] Snapshot saved: {snapshot_path}")


def get_league_models():

    return glob.glob(os.path.join(LEAGUE_DIR, "snapshot_*.pt"))


def _cpu_state_dict(net):
    return {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}


def _get_num_actors(default=4, reserve_cpus=2):
    value = os.environ.get("NUM_ACTORS")
    if value:
        try:
            return max(1, int(value))
        except ValueError:
            return default

    slurm_cpus = os.environ.get("SLURM_CPUS_PER_TASK")
    if slurm_cpus:
        try:
            return max(1, int(slurm_cpus) - reserve_cpus)
        except ValueError:
            return default

    return default


# ==========================================================
# OPPONENT DISCOVERY
# ==========================================================

def build_opponents(n_opponents, available_bots):

    opponents = list(REQUIRED_BOTS)

    required_types = {type(bot) for bot in REQUIRED_BOTS}
    pool = [bot for bot in available_bots if type(bot) not in required_types]

    league_models = get_league_models()

    for _ in range(max(0, n_opponents - len(opponents))):

        r = random.random()

        if r < 0.3 and league_models:
            model_path = random.choice(league_models)
            opponents.append(
                SnapshotPudzian(
                    model_path,
                    f"Snapshot_{random.randint(0,10000)}"
                )
            )

        elif r < 0.7:
            if pool:
                opponents.append(
                    random.choice(pool)
                )
            else:
                opponents.append(
                    random_controller.RandomController("Rand")
                )

        else:
            opponents.append(
                random_controller.RandomController("Rand")
            )

    return opponents


# ==========================================================
# ACTOR
# ==========================================================

def _ape_x_epsilon(actor_id, num_actors, eps_base=0.4, alpha=3.0):
    """Ape-X: ε_i = ε_base^(1 + i·α/(N-1)).

    Aktor 0 eksploruje najbardziej (≈ eps_base), aktor N-1 prawie greedy.
    Z α=3 i N=4 daje: 0.40, 0.16, 0.064, 0.026.
    """
    if num_actors <= 1:
        return eps_base
    exponent = 1.0 + (actor_id * alpha) / (num_actors - 1)
    return eps_base ** exponent


def actor_process(actor_id, num_actors, queue, weights_dict, stop_event):

    random.seed(actor_id + int(time.time()))
    torch.manual_seed(actor_id)

    agent = Pudzian(
        f"Actor_{actor_id}",
        brain_mode="actor",
        transition_queue=queue,
        device="cpu",            # aktor robi tylko inferencję — bez CUDA context
        load_from_disk=False,    # wagi przyjdą z weights_dict
    )
    agent.is_evaluating = False

    # Stały, zróżnicowany epsilon per aktor (Ape-X style)
    fixed_epsilon = _ape_x_epsilon(actor_id, num_actors)
    agent.brain.epsilon = fixed_epsilon
    agent.brain.epsilon_min = fixed_epsilon  # blokujemy zanik u aktora
    print(f"[ACTOR {actor_id}] epsilon = {fixed_epsilon:.4f}")

    games_played = 0
    sync_interval_games = 5  # sync wag co N gier

    while not stop_event.is_set():

        # synchronizacja wag co kilka gier (a nie co 2000)
        if games_played % sync_interval_games == 0 and "online" in weights_dict:
            try:
                agent.brain.online_net.load_state_dict(weights_dict["online"])
            except Exception as exc:
                print(f"[ACTOR {actor_id}] sync error: {exc}")

        arena = random.choice(ARENAS)
        opponents = build_opponents(7, AVAILABLE_BOTS)
        controllers = [agent] + opponents

        game = games.Game(
            game_no=random.randint(0, 1_000_000),
            arena_name=arena,
            to_spawn=controllers,
        )

        while not game.finished:
            game.cycle()

        # terminal reward
        scores = game.score()
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        placement = next(
            idx + 1
            for idx, (c, _) in enumerate(sorted_scores)
            if c == agent
        )

        placement_ratio = 1.0 - (placement - 1) / max(len(controllers) - 1, 1)
        terminal_score = (placement_ratio - 0.5) * 20

        agent.praise(terminal_score)

        games_played += 1


# ==========================================================
# EWALUACJA (osobny proces — nie blokuje learnera)
# ==========================================================

def run_evaluation(model_state_dict, available_bots, n_games=50):

    evaluator = Pudzian(
        "Evaluator",
        brain_mode="actor",
        device="cpu",
        load_from_disk=False,
    )
    evaluator.brain.online_net.load_state_dict(model_state_dict)
    evaluator.brain.epsilon = 0.0
    evaluator.is_evaluating = True

    wins = 0
    top3 = 0

    for i in range(n_games):

        arena = random.choice(ARENAS)
        opponents = build_opponents(7, AVAILABLE_BOTS)
        controllers = [evaluator] + opponents

        game = games.Game(
            game_no=10_000 + i,
            arena_name=arena,
            to_spawn=controllers,
        )

        while not game.finished:
            game.cycle()

        scores = game.score()
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        placement = next(
            idx + 1
            for idx, (c, _) in enumerate(sorted_scores)
            if c == evaluator
        )

        if placement == 1:
            wins += 1
        if placement <= 3:
            top3 += 1

    return {
        "win_rate": wins / n_games,
        "top3_rate": top3 / n_games,
    }


def evaluation_worker(model_state_dict, n_games):
    """Wrapper uruchamiany w osobnym procesie."""
    metrics = run_evaluation(model_state_dict, AVAILABLE_BOTS, n_games)
    print(
        f"[EVAL] win={metrics['win_rate']:.2%} "
        f"top3={metrics['top3_rate']:.2%}"
    )


# ==========================================================
# LEARNER
# ==========================================================

def learner_process(queue, weights_dict, stop_event):
    total_transitions = 0
    total_updates = 0
    last_log_time = time.time()
    last_snapshot_time = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    agent = Pudzian("Learner", brain_mode="learner", device=device)
    brain = agent.brain

    print("Learner started")

    last_eval_time = time.time()
    last_save_time = time.time()
    last_broadcast_time = 0.0  # od razu broadcastuj na starcie
    broadcast_interval_sec = 5.0  # broadcast wag nie częściej niż co 5s

    eval_process = None
    EVAL_INTERVAL_SEC = 1800  # 5 min (był bug: 120s + komentarz mówił 60min)

    while not stop_event.is_set():
        if time.time() - last_snapshot_time > 7200:
            tag = int(time.time())
            save_snapshot(brain, tag)
            last_snapshot_time = time.time()

        # zbieranie transitionów
        collected = 0
        for _ in range(2000):
            if queue.empty():
                break
            transition = queue.get()
            brain.replay_buffer.push(*transition)
            collected += 1

        total_transitions += collected

        # trening
        if len(brain.replay_buffer) > brain.train_start:
            for _ in range(16):
                loss = brain.train_step()
                if loss is not None:
                    total_updates += 1

        # broadcast wag — co broadcast_interval_sec, nie co iterację.
        # Pickujemy świeży CPU-clone, żeby nie dzielić tensorów CUDA między procesami.
        if time.time() - last_broadcast_time > broadcast_interval_sec:
            weights_dict["online"] = _cpu_state_dict(brain.online_net)
            last_broadcast_time = time.time()

        # checkpoint co 30 min
        if time.time() - last_save_time > 1800:
            brain.save()
            print("Checkpoint saved")
            last_save_time = time.time()

        # sprzątnij poprzedni eval_process jeśli zakończony
        if eval_process is not None and not eval_process.is_alive():
            eval_process.join()
            eval_process = None

        # uruchom nowy eval w tle (nie blokuje treningu)
        if eval_process is None and time.time() - last_eval_time > EVAL_INTERVAL_SEC:
            print("[EVAL] launching evaluation in background...")
            eval_process = mp.Process(
                target=evaluation_worker,
                args=(_cpu_state_dict(brain.online_net), 50),
                daemon=False,
            )
            eval_process.start()
            last_eval_time = time.time()

        if time.time() - last_log_time > 10:

            buffer_size = (
                len(brain.replay_buffer)
                if brain.replay_buffer is not None
                else 0
            )

            print(
                f"[LEARNER] "
                f"transitions={total_transitions} | "
                f"buffer={buffer_size} | "
                f"updates={total_updates} | "
                f"epsilon={brain.epsilon:.3f}"
            )

            last_log_time = time.time()

    # graceful shutdown — poczekaj na eval w tle (max 30s)
    if eval_process is not None and eval_process.is_alive():
        eval_process.join(timeout=30)


class SnapshotPudzian(Pudzian):

    def __init__(self, model_path, name):
        # actor mode + CPU = brak ReplayBuffera/target/optim + brak CUDA context
        super().__init__(
            name,
            brain_mode="actor",
            device="cpu",
            load_from_disk=False,
        )

        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        self.brain.online_net.load_state_dict(checkpoint["online_net"])

        self.brain.epsilon = 0.0
        self.is_evaluating = True


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ogranicz liczbę wątków PyTorch/BLAS, żeby uniknąć oversubscription
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)

    mp.set_start_method("spawn")

    num_actors = _get_num_actors()

    manager = mp.Manager()
    weights_dict = manager.dict()
    # rozmiar kolejki proportionalny do liczby aktorów (unikamy dropów)
    queue_size = max(300_000, num_actors * 20_000)
    transition_queue = mp.Queue(maxsize=queue_size)
    stop_event = mp.Event()

    init_agent = Pudzian(
        "Init",
        brain_mode="actor",
        device="cpu",
    )
    weights_dict["online"] = _cpu_state_dict(init_agent.brain.online_net)
    del init_agent

    learner = mp.Process(
        target=learner_process,
        args=(transition_queue, weights_dict, stop_event),
    )
    learner.start()

    actors = []
    for i in range(num_actors):
        p = mp.Process(
            target=actor_process,
            args=(i, num_actors, transition_queue, weights_dict, stop_event),
        )
        p.start()
        actors.append(p)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop_event.set()

    for p in actors:
        p.join()
    learner.join()


if __name__ == "__main__":
    main()
