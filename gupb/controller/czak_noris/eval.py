"""
Ewaluacja bota bez nauki (epsilon = 0, brak aktualizacji Q).

Użycie (z katalogu głównego repo):
    python -m gupb.controller.czak_noris.eval new 200
    python -m gupb.controller.czak_noris.eval noq 200
    python -m gupb.controller.czak_noris.eval file:ścieżka/do/wersji.py 200
"""
import importlib.util
import logging
import random
import sys
from statistics import mean, stdev

logging.getLogger("verbose").setLevel(logging.CRITICAL)
logging.disable(logging.WARNING)

from gupb.controller import benjamin_netanyahu
from gupb.controller import bigbot
from gupb.controller import biwakspot
from gupb.controller import blade_runner
from gupb.controller import bob
from gupb.controller import jeffrey_e
from gupb.controller import karakin
from gupb.controller import pudzian
from gupb.controller import random as random_ctrl
from gupb.controller import syntax_terror
from gupb.controller import the_trooper
from gupb.controller.czak_noris.czak_noris import CzakNoris
from gupb.model import games

# mapy hold-out z arena_generator - nieużywane w treningu, jak nieznane mapy turnieju
ARENA_NAMES = [f"generated_eval_{i}" for i in range(10)]


def build_opponents() -> list:
    return [
        random_ctrl.RandomController("Alice"),
        benjamin_netanyahu.BenjaminNetanyahu("BenjaminNetanyahu"),
        karakin.KarakinController("Karakin"),
        blade_runner.BladeRunner("BladeRunner"),
        jeffrey_e.jeffrey_e_controller.JeffreyEController("JeffreyE"),
        bigbot.BIGbot("BIGbot"),
        bob.Bob("BobMinion"),
        the_trooper.TheTrooper("The Trooper"),
        pudzian.Pudzian("Pudzian"),
        biwakspot.biwakspot_controller.BiwakSpot("BiwakSpot"),
        syntax_terror.SyntaxTerror("Syntax Terror"),
    ]


def load_variant(spec: str):
    if spec == "new":
        bot = CzakNoris("CzakNoris", use_qtable=True)
        bot.q.epsilon = 0.0
        return bot
    if spec == "noq":
        bot = CzakNoris("CzakNoris", use_qtable=False)
        bot.q.epsilon = 0.0
        return bot
    if spec.startswith("file:"):
        path = spec[len("file:"):]
        module_spec = importlib.util.spec_from_file_location(
            "czak_noris_variant", path
        )
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module.CzakNoris("CzakNoris")
    raise SystemExit(f"Nieznany wariant: {spec}")


def main() -> None:
    variant = sys.argv[1] if len(sys.argv) > 1 else "new"
    n_games = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    bot = load_variant(variant)
    opponents = build_opponents()

    results = []
    for i in range(n_games):
        random.seed(10_000 + i)
        field = [bot] + opponents
        random.shuffle(field)
        try:
            game = games.Game(
                game_no=i,
                arena_name=ARENA_NAMES[i % len(ARENA_NAMES)],
                to_spawn=field,
            )
            while not game.finished:
                game.cycle()
            scores = game.score()
        except Exception as exc:
            print(f"Błąd w grze {i}: {exc!r}", flush=True)
            continue
        our_score = scores.get(bot, 0)
        place = 1 + sum(1 for s in scores.values() if s > our_score)
        results.append((our_score, place))
        for ctrl, score in scores.items():
            try:
                ctrl.praise(score)
            except Exception:
                pass
        if (i + 1) % 25 == 0:
            done = [r[0] for r in results]
            print(
                f"  {i + 1}/{n_games} gier, śr. score {mean(done):.2f}",
                flush=True,
            )

    if not results:
        print("Brak ukończonych gier.")
        return
    scores_list = [r[0] for r in results]
    places = [r[1] for r in results]
    n = len(results)
    se = stdev(scores_list) / n ** 0.5 if n > 1 else 0.0
    wins = sum(1 for p in places if p == 1)
    top3 = sum(1 for p in places if p <= 3)
    print("=" * 60)
    print(f"Wariant: {variant} | gier: {n}")
    print(f"Suma punktów:    {sum(scores_list)}")
    print(f"Średni score:    {mean(scores_list):.2f} ± {se:.2f} (SE)")
    print(f"Średnie miejsce: {mean(places):.2f}")
    print(f"Wygrane:         {wins} ({wins / n:.0%})")
    print(f"Top-3:           {top3} ({top3 / n:.0%})")


if __name__ == "__main__":
    main()
