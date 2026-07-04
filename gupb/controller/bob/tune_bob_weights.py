"""Offline tuning wag Boba
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np
from scipy.optimize import differential_evolution

from gupb.model import games
from gupb.controller.bob.bob import Bob
from gupb.controller.bob.bob_weights import (
    BOUNDS,
    PARAM_NAMES,
    DEFAULT_WEIGHTS,
    weights_from_vector,
)

MAX_CYCLES = 40000
BOB_DIR = Path(__file__).resolve().parent


def build_opponents(names: List[str]) -> List[object]:
    def _random():
        from gupb.controller import random as m
        return m.RandomController("Alice")

    def _czak():
        from gupb.controller import czak_noris as m
        return m.czak_noris.CzakNoris("CzakNoris")

    def _trooper():
        from gupb.controller import the_trooper as m
        return m.TheTrooper("The Trooper")

    def _biwak():
        from gupb.controller import biwakspot as m
        return m.biwakspot_controller.BiwakSpot("BiwakSpot")

    def _benjamin():
        from gupb.controller import benjamin_netanyahu as m
        return m.BenjaminNetanyahu("BenjaminNetanyahu")

    registry: Dict[str, Callable[[], object]] = {
        "random": _random,
        "czak_noris": _czak,
        "the_trooper": _trooper,
        "biwakspot": _biwak,
        "benjamin": _benjamin,
    }
    out = []
    for name in names:
        factory = registry.get(name)
        if factory is None:
            print(f"[warn] nieznany przeciwnik: {name}")
            continue
        try:
            out.append(factory())
        except Exception as e:
            print(f"[warn] nie zbudowano {name}: {e!r}")
    return out


def available_arenas(requested: List[str]) -> List[str]:
    ok = []
    for name in requested:
        if os.path.exists(os.path.join("resources", "arenas", f"{name}.gupb")):
            ok.append(name)
        else:
            print(f"[warn] brak areny: {name}.gupb")
    return ok


def run_one_game(bob: Bob, opponents: List[object], arena_name: str, seed: int) -> float:
    """Rozgrywa gre in-memory i zwraca placement Boba znormalizowany do 0-1"""
    random.seed(seed)
    to_spawn = [bob] + list(opponents)
    random.shuffle(to_spawn)
    try:
        game = games.Game(game_no=0, arena_name=arena_name, to_spawn=to_spawn)
        cycles = 0
        while not game.finished and cycles < MAX_CYCLES:
            game.cycle()
            cycles += 1
        if not game.finished:
            return 0.0
        scores = game.score()
    except Exception:
        return 0.0
    bob_score = None
    max_score = 1
    for ctrl, sc in scores.items():
        if sc > max_score:
            max_score = sc
        if ctrl is bob:
            bob_score = sc
    return 0.0 if bob_score is None else bob_score / max_score


def make_schedule(arenas: List[str], n_games: int, base_seed: int) -> List[Tuple[str, int]]:
    """Staly harmonogram wspólny dla wszystkich kandydatow (CRN)"""
    rng = random.Random(base_seed)
    return [(arenas[i % len(arenas)], rng.randint(0, 2_000_000_000)) for i in range(n_games)]


def evaluate_weights(weights: Dict[str, float], opponents_names: List[str], schedule: List[Tuple[str, int]]) -> float:
    scores = []
    for arena, seed in schedule:
        opponents = build_opponents(opponents_names)
        if not opponents:
            return 0.0
        scores.append(run_one_game(Bob("Bob", weights=weights), opponents, arena, seed))
    return float(np.mean(scores)) if scores else 0.0


class Objective:
    """Funkcja celu DE: -mean_score, z logiem JSONL każdego kandydata"""

    def __init__(self, opponents_names, schedule, log_path):
        self.opponents_names = opponents_names
        self.schedule = schedule
        self.evals = 0
        self.best = float("-inf")
        self.best_vector = None
        self._log = open(log_path, "w", encoding="utf-8")

    def __call__(self, vector) -> float:
        self.evals += 1
        weights = weights_from_vector(list(vector))
        try:
            mean_score = evaluate_weights(weights, self.opponents_names, self.schedule)
        except Exception as e:
            print(f"[warn] kandydat padl: {e!r}")
            mean_score = 0.0
        self._log.write(json.dumps({"eval": self.evals, "mean_score": mean_score, "weights": weights}) + "\n")
        self._log.flush()
        if mean_score > self.best:
            self.best = mean_score
            self.best_vector = list(vector)
            print(f"[eval {self.evals}] NEW BEST mean_score={mean_score:.4f}")
        else:
            print(f"[eval {self.evals}] mean_score={mean_score:.4f} (best={self.best:.4f})")
        return -mean_score

    def close(self):
        self._log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline tuning wag Boba (differential_evolution).")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--games-per-candidate", type=int, default=None)
    parser.add_argument("--reeval-games", type=int, default=None)
    parser.add_argument("--maxiter", type=int, default=None)
    parser.add_argument("--popsize", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=str(BOB_DIR / "bob_best_weights.json"))
    parser.add_argument("--log", type=str, default=str(BOB_DIR / "bob_tuning_log.jsonl"))
    parser.add_argument("--arenas", type=str, default=",".join(f"generated_{i}" for i in range(10)))
    parser.add_argument("--opponents", type=str, default="random,czak_noris,the_trooper,biwakspot,benjamin")
    args = parser.parse_args()

    if args.quick:
        gpc, maxiter, popsize, reeval = args.games_per_candidate or 4, args.maxiter or 8, args.popsize or 3, args.reeval_games or 12
    elif args.full:
        gpc, maxiter, popsize, reeval = args.games_per_candidate or 10, args.maxiter or 60, args.popsize or 6, args.reeval_games or 40
    else:
        gpc, maxiter, popsize, reeval = args.games_per_candidate or 6, args.maxiter or 25, args.popsize or 4, args.reeval_games or 20

    random.seed(args.seed)
    np.random.seed(args.seed)

    arenas = available_arenas([a.strip() for a in args.arenas.split(",") if a.strip()])
    if not arenas:
        print("[error] brak aren. Wygeneruj: python -m gupb.scripts.arena_generator")
        sys.exit(1)
    opponents_names = [o.strip() for o in args.opponents.split(",") if o.strip()]
    if not build_opponents(opponents_names):
        print("[error] nie zbudowano zadnego przeciwnika.")
        sys.exit(1)

    schedule = make_schedule(arenas, gpc, args.seed)
    print(f"[info] areny={arenas}")
    print(f"[info] przeciwnicy={opponents_names} gier/kandydata={gpc} maxiter={maxiter} popsize={popsize}")
    baseline = evaluate_weights(DEFAULT_WEIGHTS, opponents_names, schedule)
    print(f"[info] baseline (DEFAULT_WEIGHTS) mean_score={baseline:.4f}")

    objective = Objective(opponents_names, schedule, args.log)
    t0 = time.time()
    result = differential_evolution(
        objective, BOUNDS, maxiter=maxiter, popsize=popsize, seed=args.seed,
        polish=False, tol=0.01, mutation=(0.5, 1.0), recombination=0.7,
        init="latinhypercube", workers=1, updating="immediate",
    )
    objective.close()
    best_vector = result.x if objective.best_vector is None else objective.best_vector
    print(f"[info] DE done in {time.time() - t0:.1f}s, evals={objective.evals}")

    reeval_schedule = make_schedule(arenas, reeval, args.seed + 999983)
    reeval_score = evaluate_weights(weights_from_vector(list(best_vector)), opponents_names, reeval_schedule)
    print(f"[info] reeval mean_score={reeval_score:.4f} (tuning best={objective.best:.4f}, baseline={baseline:.4f})")

    best_weights = weights_from_vector(list(best_vector))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "mean_score_tuning": objective.best, "mean_score_reeval": reeval_score, "baseline": baseline,
            "opponents": opponents_names, "arenas": arenas, "games_per_candidate": gpc,
            "seed": args.seed, "param_names": PARAM_NAMES, "weights": best_weights,
        }, f, indent=2)
    print(f"[info] zapisano najlepsze wagi do {args.output}")
    print("[info] wklej do BEST_WEIGHTS w bob_weights.py:")
    print(json.dumps(best_weights, indent=2))


if __name__ == "__main__":
    main()
