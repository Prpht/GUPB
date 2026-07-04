"""
Trening bota Pudzian — Dueling Double DQN z curriculum learning.
Wspiera przetwarzanie wielordzeniowe (Ape-X style) oraz system ligi (SnapshotPudzian).
"""

import logging
import random
import os
import csv
import time
import shutil
import glob
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from tqdm import trange, tqdm

import torch
import torch.multiprocessing as mp

from gupb.model import games
from gupb.controller import random as random_controller
from gupb.controller.pudzian.pudzian import Pudzian

from gupb.controller.benjamin_netanyahu.benjamin_netanyahu import BenjaminNetanyahu
from gupb.controller.biwakspot.biwakspot_controller import BiwakSpot
from gupb.controller.bigbot.bigbot import BIGbot
from gupb.controller.bob.bob import Bob
from gupb.controller.czak_noris.czak_noris import CzakNoris
from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController
from gupb.controller.karakin.karakin_controller import KarakinController
from gupb.controller.syntax_terror.syntax_terror import SyntaxTerror
from gupb.controller.the_trooper.the_trooper_controller import TheTrooper

logger = logging.getLogger(__name__)

_PUDZIAN_DIR = os.path.dirname(__file__)
LEAGUE_DIR = os.path.join(_PUDZIAN_DIR, "league")
os.makedirs(LEAGUE_DIR, exist_ok=True)

def get_league_models():
    return glob.glob(os.path.join(LEAGUE_DIR, "snapshot_*.pt"))

def save_snapshot(brain, tag):
    snapshot_path = os.path.join(LEAGUE_DIR, f"snapshot_{tag}.pt")
    snapshots = sorted(get_league_models(), key=os.path.getmtime)
    if len(snapshots) > 10:
        os.remove(snapshots[0])
    brain.save()
    shutil.copy2(brain.model_path, snapshot_path)
    # tqdm.write(f"[LEAGUE] Zapisano snapshot: {snapshot_path}")

class SnapshotPudzian(Pudzian):
    def __init__(self, model_path, name):
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

def get_all_bots():
    return [
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

@dataclass
class DifficultyLevel:
    name: str
    n_opponents: int
    bot_ratio: float
    arenas: List[str]
    min_games: int
    target_top3: Optional[float]

LEVELS = [
    DifficultyLevel(
        name="ROOKIE",
        n_opponents=4,
        bot_ratio=0.0,
        arenas=["ordinary_chaos"],
        min_games=120,
        target_top3=0.65,
    ),
    DifficultyLevel(
        name="AMATEUR",
        n_opponents=7,
        bot_ratio=0.25,
        arenas=["ordinary_chaos", "lone_sanctum", "isolated_shrine"],
        min_games=200,
        target_top3=0.38,
    ),
    DifficultyLevel(
        name="VETERAN",
        n_opponents=10,
        bot_ratio=0.55,
        arenas=["ordinary_chaos", "lone_sanctum", "isolated_shrine", "dungeon"],
        min_games=300,
        target_top3=0.25,
    ),
    DifficultyLevel(
        name="ELITE",
        n_opponents=10,
        bot_ratio=0.80,
        arenas=["ordinary_chaos", "lone_sanctum", "isolated_shrine", "dungeon", "wasteland", "archipelago"],
        min_games=0,
        target_top3=None,
    ),
]

class CurriculumManager:
    WINDOW = 50
    STAGNATION = 200

    def __init__(self):
        self.level_idx = 0
        self.games_at_level = 0
        self.recent_top3 = deque(maxlen=self.WINDOW)
        self.best_top3_at_level = 0.0
        self.stagnation_counter = 0

    @property
    def level(self) -> DifficultyLevel:
        return LEVELS[self.level_idx]

    @property
    def level_name(self) -> str:
        return self.level.name

    def rolling_top3(self) -> float:
        if not self.recent_top3:
            return 0.0
        return sum(self.recent_top3) / len(self.recent_top3)

    def record(self, placement: int, n_total: int) -> bool:
        top3 = 1 if placement <= max(3, n_total // 4) else 0
        self.recent_top3.append(top3)
        self.games_at_level += 1

        current_top3 = self.rolling_top3()
        if current_top3 > self.best_top3_at_level:
            self.best_top3_at_level = current_top3
            self.stagnation_counter = 0
        else:
            self.stagnation_counter += 1

        lvl = self.level
        if (lvl.target_top3 is not None
                and self.games_at_level >= lvl.min_games
                and len(self.recent_top3) == self.WINDOW
                and current_top3 >= lvl.target_top3):
            self._advance()
            return True
        return False

    def _advance(self):
        self.level_idx = min(self.level_idx + 1, len(LEVELS) - 1)
        self.games_at_level = 0
        self.recent_top3.clear()
        self.best_top3_at_level = 0.0
        self.stagnation_counter = 0

def build_opponents(n_opponents: int, bot_ratio: float) -> list:
    opponents = []
    # Zawsze dodajemy tych dwóch kluczowych przeciwników
    opponents.append(BenjaminNetanyahu("B_Netanyahu"))
    opponents.append(BiwakSpot("B_Spot"))
    
    available_bots = get_all_bots()
    # Usuwamy ich z puli losowania, żeby się nie powtarzali
    available_bots = [b for b in available_bots if not isinstance(b, (BenjaminNetanyahu, BiwakSpot))]
    
    # Obliczamy ilu jeszcze "inteligentnych" botów potrzebujemy (uwzględniając już dodanych 2)
    # n_real to docelowa liczba botów nie-losowych
    target_real = int(n_opponents * bot_ratio)
    remaining_real = max(0, target_real - len(opponents))
    
    league_models = get_league_models()
    
    for _ in range(remaining_real):
        r = random.random()
        # 30% szans na wylosowanie dawnego Pudziana z ligi
        if r < 0.3 and league_models:
            model_path = random.choice(league_models)
            opponents.append(SnapshotPudzian(model_path, f"Snap_{random.randint(0,999)}"))
        else:
            if available_bots:
                bot = random.choice(available_bots)
                available_bots.remove(bot)
                opponents.append(bot)

    # Dopełniamy resztę losowymi kontrolerami do limitu n_opponents
    while len(opponents) < n_opponents:
        opponents.append(random_controller.RandomController(f"Rand_{len(opponents)}"))
        
    return opponents

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
    import multiprocessing as mp
    return max(1, mp.cpu_count() - reserve_cpus)

def _ape_x_epsilon(actor_id, num_actors, eps_base=0.4, alpha=3.0):
    if num_actors <= 1:
        return eps_base
    exponent = 1.0 + (actor_id * alpha) / (num_actors - 1)
    return eps_base ** exponent

def actor_process(actor_id, num_actors, queue, weights_dict, results_queue, stop_event):
    # Przy spawn procesy-dzieci NIE dziedziczą torch.set_num_threads(1) z
    # run_training. Ograniczamy wątki w każdym aktorze, by N aktorów nie
    # przesubskrybowało rdzeni (każdy odpalałby pełną pulę intra-op).
    # (Historycznie to też łagodziło bug wielowątkowego torch.nonzero w
    # choose_action — ten kernel został już z gorącej ścieżki usunięty.)
    torch.set_num_threads(1)
    random.seed(actor_id + int(time.time()))
    torch.manual_seed(actor_id)

    agent = Pudzian(
        f"Actor_{actor_id}",
        brain_mode="actor",
        transition_queue=queue,
        device="cpu",
        load_from_disk=False,
    )
    agent.is_evaluating = False

    fixed_epsilon = _ape_x_epsilon(actor_id, num_actors)
    agent.brain.epsilon = fixed_epsilon
    agent.brain.epsilon_min = fixed_epsilon
    print(f"[ACTOR {actor_id}] epsilon = {fixed_epsilon:.4f}")

    games_played = 0
    sync_interval_games = 5

    while not stop_event.is_set():
        # Warmup: dopóki learner zbiera startowy bufor, gramy CZYSTO losowo
        # (epsilon=1.0). Maska + heurystyki sprawiają, że losowe taktyki dają
        # zróżnicowane, ale grywalne epizody — idealny bootstrap dla PER.
        # Po warmupie wracamy do stałego epsilona Ape-X dla tego aktora.
        agent.brain.epsilon = 1.0 if weights_dict.get("warmup", True) else fixed_epsilon

        if games_played % sync_interval_games == 0 and "online" in weights_dict:
            try:
                agent.brain.online_net.load_state_dict(weights_dict["online"])
            except Exception:
                pass
        
        lvl_idx = weights_dict.get("level_idx", 0)
        lvl = LEVELS[lvl_idx]

        arena = random.choice(lvl.arenas)
        opponents = build_opponents(lvl.n_opponents, lvl.bot_ratio)
        controllers = [agent] + opponents

        game = games.Game(
            game_no=random.randint(0, 1_000_000),
            arena_name=arena,
            to_spawn=controllers,
        )

        while not game.finished:
            game.cycle()

        scores = game.score()
        pudzian_score = scores.get(agent, 0)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        placement = next(
            idx + 1 for idx, (c, _) in enumerate(sorted_scores) if c == agent
        )
        n_total = len(controllers)

        placement_ratio = 1.0 - (placement - 1) / max(n_total - 1, 1)
        terminal_score = round((placement_ratio - 0.5) * 60)
        agent.praise(terminal_score)

        win = 1 if placement == 1 else 0
        
        results_queue.put({
            "placement": placement,
            "n_total": n_total,
            "win": win,
            "score": pudzian_score,
            "arena": arena,
            "level": lvl.name,
            "epsilon": fixed_epsilon
        })

        games_played += 1

def run_evaluation(model_state_dict, n_games=50):
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
    placements = []
    
    eval_arenas = ["ordinary_chaos", "lone_sanctum", "isolated_shrine", "dungeon"]

    for i in range(n_games):
        arena = random.choice(eval_arenas)
        opponents = build_opponents(10, 0.50)
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
            idx + 1 for idx, (c, _) in enumerate(sorted_scores) if c == evaluator
        )

        wins += 1 if placement == 1 else 0
        top3 += 1 if placement <= max(3, len(controllers) // 4) else 0
        placements.append(placement)

    n = max(len(placements), 1)
    return {
        "win_rate": wins / n,
        "top3_rate": top3 / n,
        "avg_placement": np.mean(placements) if placements else 0,
    }

def evaluation_worker(model_state_dict, n_games, results_dict):
    metrics = run_evaluation(model_state_dict, n_games)
    print(
        f"[EVAL] win={metrics['win_rate']:.2%} "
        f"top3={metrics['top3_rate']:.2%} "
        f"avg_place={metrics['avg_placement']:.2f}"
    )
    results_dict["eval_metrics"] = metrics

def learner_process(transition_queue, weights_dict, results_queue, stop_event, iterations=80_000, eval_interval=500):
    torch.set_num_threads(1)  # spawn nie dziedziczy ustawienia z run_training
    device = "cuda" if torch.cuda.is_available() else "cpu"
    agent = Pudzian("Learner", brain_mode="learner", device=device)
    brain = agent.brain

    print(f"Learner started on {device}")

    # Faza warmup: aktorzy grają czysto losowo (epsilon=1.0), dopóki bufor
    # nie zbierze WARMUP_TRANSITIONS zróżnicowanych przejść. (Epsilon learnera
    # jest nieużywany — learner nie gra; eksploracja żyje wyłącznie w aktorach.)
    WARMUP_TRANSITIONS = 30_000
    weights_dict["warmup"] = True

    # Ile aktualizacji gradientu na zebrane przejście (replay ratio). GPU jest
    # wolne (wąskie gardło = symulacja gier), więc stać nas na ~4× dla lepszej
    # efektywności próbkowej — bez przesady, by uniknąć przeuczenia bufora.
    REPLAY_RATIO = 4

    curriculum = CurriculumManager()
    weights_dict["level_idx"] = curriculum.level_idx

    train_csv = os.path.join(_PUDZIAN_DIR, "training_log.csv")
    with open(train_csv, "w", newline="") as f:
        csv.writer(f).writerow([
            "Game", "Level", "Arena", "Opponents", "Score",
            "Placement", "Win", "Top3_rolling", "Epsilon", "Loss",
        ])

    eval_csv = os.path.join(_PUDZIAN_DIR, "eval_log.csv")
    with open(eval_csv, "w", newline="") as f:
        csv.writer(f).writerow([
            "Game", "WinRate", "Top3Rate", "AvgPlacement",
        ])

    level_stats = {lvl.name: {"games": 0, "wins": 0, "top3": 0, "placements": []}
                   for lvl in LEVELS}
    best_eval_top3 = 0.0
    recent_losses = deque(maxlen=100)

    total_transitions = 0
    total_updates = 0
    games_processed = 0
    # Ułamkowy „kredyt" aktualizacji — utrzymuje DOKŁADNY replay ratio niezależnie
    # od tego, ile przejść wpadło w danej iteracji. Zastępuje max(1, …), które
    # podczas zastoju kolejki (collected=0) wymuszało update na nieświeżym
    # buforze i de facto rozdmuchiwało replay ratio ponad REPLAY_RATIO.
    update_credit = 0.0

    last_broadcast_time = 0.0
    broadcast_interval_sec = 5.0
    last_snapshot_time = time.time()

    eval_process = None
    manager = mp.Manager()
    eval_results_dict = manager.dict()

    pbar = tqdm(total=iterations, desc="Trening")
    last_eval_game = 0

    while not stop_event.is_set() and games_processed < iterations:
        # League snapshot
        if time.time() - last_snapshot_time > 3600:  # Co godzine
            save_snapshot(brain, int(time.time()))
            last_snapshot_time = time.time()

        collected = 0
        for _ in range(2000):
            if transition_queue.empty():
                break
            transition = transition_queue.get()
            brain.replay_buffer.push(*transition)
            collected += 1
        
        total_transitions += collected

        # Zakończ warmup, gdy bufor ma dość zróżnicowanych przejść.
        if weights_dict.get("warmup", True) and total_transitions >= WARMUP_TRANSITIONS:
            weights_dict["warmup"] = False
            tqdm.write(f"\n  [WARMUP] Zakończony ({total_transitions} przejść) — aktorzy przechodzą na epsilon Ape-X")

        if len(brain.replay_buffer) > brain.train_start:
            # Liczba kroków powiązana z napływem danych — stały replay ratio
            # niezależnie od liczby aktorów (brak dropów przy wielu aktorach,
            # brak przeuczenia przy lulli w kolejce). Kredyt ułamkowy gwarantuje,
            # że średnio robimy collected*REPLAY_RATIO/batch updatów — bez floora
            # ≥1, który podczas pustej kolejki trenował na nieświeżym buforze.
            update_credit += (collected * REPLAY_RATIO) / brain.batch_size
            n_updates = int(update_credit)
            update_credit -= n_updates
            for _ in range(n_updates):
                loss = brain.train_step()
                if loss is not None:
                    recent_losses.append(loss)
                    total_updates += 1

        if time.time() - last_broadcast_time > broadcast_interval_sec:
            weights_dict["online"] = _cpu_state_dict(brain.online_net)
            last_broadcast_time = time.time()

        while not results_queue.empty():
            res = results_queue.get()
            games_processed += 1
            pbar.update(1)

            placement = res["placement"]
            n_total = res["n_total"]

            # Awans curriculum liczymy TYLKO z gier near-greedy aktorów
            # (epsilon ≤ 0.10). Wysokoeksploracyjni aktorzy (np. 0.40) zaniżają
            # top3 i zaszumiają próg awansu — okno powinno mierzyć faktyczną
            # politykę, nie eksplorację. Wszystkie gry trafiają do CSV niżej.
            if res["epsilon"] <= 0.10:
                advanced = curriculum.record(placement, n_total)
            else:
                advanced = False
            top3_roll = curriculum.rolling_top3()
            
            if advanced:
                weights_dict["level_idx"] = curriculum.level_idx
                tqdm.write(f"\n  >>> AWANS: {LEVELS[curriculum.level_idx - 1].name} → {curriculum.level_name} (gra {games_processed}, top3={top3_roll:.0%})")
            
            loss_avg = np.mean(recent_losses) if recent_losses else 0.0

            with open(train_csv, "a", newline="") as f:
                csv.writer(f).writerow([
                    games_processed, res["level"], res["arena"], n_total,
                    res["score"], placement, res["win"],
                    f"{top3_roll:.3f}", f"{res['epsilon']:.4f}",
                    f"{loss_avg:.4f}",
                ])

            lvl_name = res["level"]
            if lvl_name in level_stats:
                ls = level_stats[lvl_name]
                ls["games"] += 1
                ls["wins"] += res["win"]
                ls["top3"] += 1 if placement <= max(3, n_total // 4) else 0
                ls["placements"].append(placement)

            if games_processed - last_eval_game >= eval_interval:
                last_eval_game = games_processed
                if eval_process is None or not eval_process.is_alive():
                    tqdm.write(f"\n  [EVAL] Gra {games_processed} — uruchamiam ewaluację w tle...")
                    eval_process = mp.Process(
                        target=evaluation_worker,
                        args=(_cpu_state_dict(brain.online_net), 50, eval_results_dict),
                    )
                    eval_process.start()

            if games_processed % 5000 == 0:
                ckpt_path = os.path.join(_PUDZIAN_DIR, f"pudzian_dqn_ckpt_{games_processed}.pt")
                brain.save()
                shutil.copy2(brain.model_path, ckpt_path)
                tqdm.write(f"\n  [CKPT] Checkpoint → {ckpt_path}")

        if "eval_metrics" in eval_results_dict:
            metrics = eval_results_dict.pop("eval_metrics")
            with open(eval_csv, "a", newline="") as f:
                csv.writer(f).writerow([
                    games_processed, f"{metrics['win_rate']:.4f}",
                    f"{metrics['top3_rate']:.4f}",
                    f"{metrics['avg_placement']:.2f}",
                ])

            if metrics['top3_rate'] > best_eval_top3:
                best_eval_top3 = metrics['top3_rate']
                best_path = os.path.join(_PUDZIAN_DIR, "pudzian_dqn_best.pt")
                brain.save()
                shutil.copy2(brain.model_path, best_path)
                tqdm.write(f"  [EVAL] ★ Nowy najlepszy model! top3={best_eval_top3:.1%} → {best_path}")

        # Pusta kolejka — oddaj CPU zamiast kręcić pętlą bez pracy.
        if collected == 0:
            time.sleep(0.002)

    pbar.close()
    
    if eval_process is not None and eval_process.is_alive():
        eval_process.join(timeout=30)
        
    print(f"\n{'='*60}")
    print(f"  RAPORT KOŃCOWY")
    print(f"{'='*60}")
    print(f"  Iteracje:        {iterations}")
    print(f"  Poziom:          {curriculum.level_name}")
    print(f"  Najlepszy eval:  top3={best_eval_top3:.1%}")
    print()

    for lvl_name, ls in level_stats.items():
        g = ls["games"]
        if g == 0:
            continue
        wr = ls["wins"] / g * 100
        t3r = ls["top3"] / g * 100
        avg = np.mean(ls["placements"])
        print(f"  {lvl_name:<10}  gry={g:>5}  win={wr:>5.1f}%  top3={t3r:>5.1f}%  avg={avg:.2f}")

    print(f"{'='*60}")

    brain.save()
    stop_event.set()

def run_training(iterations: int = 80_000, eval_interval: int = 500):
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    mp.set_start_method("spawn", force=True)

    num_actors = _get_num_actors()
    
    print(f"{'='*60}")
    print(f"  TRENING PUDZIANA (MULTIPROCESSING)")
    print(f"{'='*60}")
    print(f"  Aktorzy:           {num_actors}")
    print(f"  Iteracje:          {iterations}")
    print(f"  Ewaluacja co:      {eval_interval} gier")
    print(f"{'='*60}\n")

    manager = mp.Manager()
    weights_dict = manager.dict()
    
    queue_size = max(300_000, num_actors * 20_000)
    transition_queue = mp.Queue(maxsize=queue_size)
    results_queue = mp.Queue()
    stop_event = mp.Event()

    init_agent = Pudzian("Init", brain_mode="actor", device="cpu")
    weights_dict["online"] = _cpu_state_dict(init_agent.brain.online_net)
    del init_agent

    learner = mp.Process(
        target=learner_process,
        args=(transition_queue, weights_dict, results_queue, stop_event, iterations, eval_interval),
    )
    learner.start()

    actors = []
    for i in range(num_actors):
        p = mp.Process(
            target=actor_process,
            args=(i, num_actors, transition_queue, weights_dict, results_queue, stop_event),
        )
        p.start()
        actors.append(p)

    try:
        learner.join()
    except KeyboardInterrupt:
        stop_event.set()
        learner.join()

    for p in actors:
        p.join()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trening Pudziana (DQN - Multiprocessing)")
    parser.add_argument("-i", "--iterations", type=int, default=80_000)
    parser.add_argument("-e", "--eval-interval", type=int, default=500)
    args = parser.parse_args()
    
    run_training(iterations=args.iterations, eval_interval=args.eval_interval)
