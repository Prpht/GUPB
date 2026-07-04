"""
Trening selektora trybów (Double Q-Learning) przeciw pełnej stawce z turnieju.
Tabela Q zapisywana do czak_noris_qtable.pkl, trening można wznawiać.

Użycie (z katalogu głównego repo):
    python -m gupb.controller.czak_noris.train [liczba_gier] [--fast]
"""
import logging
import os
import random
import shutil
import sys
from collections import deque

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
from gupb.controller.czak_noris.czak_noris import MODES, QTABLE_PATH, CzakNoris
from gupb.model import games

# pula map z arena_generator (runda 2 gra na 10 nieznanych mapach z tego skryptu)
ARENA_NAMES = [f"generated_train_{i:02d}" for i in range(26)]
DEFAULT_GAMES = 20000
SAVE_EVERY = 50
BACKUP_EVERY = 1000
REPORT_EVERY = 25
EPS_START = 0.30
EPS_FLOOR = 0.05
EPS_SPAN = 5000
MAX_FAILURES = 50


def build_opponents(fast: bool) -> list:
    opponents = [
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
    ]
    if fast:
        opponents.append(random_ctrl.RandomController("Zed"))
    else:
        opponents.append(syntax_terror.SyntaxTerror("Syntax Terror"))
    return opponents


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fast = "--fast" in sys.argv
    total_games = int(args[0]) if args else DEFAULT_GAMES

    bot = CzakNoris("CzakNoris", is_training=True, use_qtable=True)
    opponents = build_opponents(fast)

    print(
        f"Start: {bot.q.games} gier w tabeli, cel {total_games}, "
        f"fast={fast}, stanów {bot.q.states_seen()}",
        flush=True,
    )

    window_scores = deque(maxlen=100)
    window_places = deque(maxlen=100)
    window_wins = deque(maxlen=100)
    last_counts = dict(bot.mode_counts)
    game_no = 0
    failures = 0

    try:
        while bot.q.games < total_games:
            bot.q.epsilon = max(
                EPS_FLOOR,
                EPS_START - (EPS_START - EPS_FLOOR) * bot.q.games / EPS_SPAN,
            )
            field = [bot] + opponents
            random.shuffle(field)
            try:
                game = games.Game(
                    game_no=game_no,
                    arena_name=random.choice(ARENA_NAMES),
                    to_spawn=field,
                )
                while not game.finished:
                    game.cycle()
                scores = game.score()
            except Exception as exc:
                failures += 1
                print(f"Błąd w grze {game_no}: {exc!r}", flush=True)
                game_no += 1
                if failures > MAX_FAILURES:
                    print("Za dużo błędów, przerywam.", flush=True)
                    break
                continue
            game_no += 1

            our_score = scores.get(bot, 0)
            place = 1 + sum(1 for s in scores.values() if s > our_score)
            for ctrl, score in scores.items():
                try:
                    ctrl.praise(score)
                except Exception:
                    pass

            window_scores.append(our_score)
            window_places.append(place)
            window_wins.append(1 if place == 1 else 0)

            if bot.q.games % SAVE_EVERY == 0:
                bot.q.save()
            if bot.q.games % BACKUP_EVERY == 0 and os.path.exists(QTABLE_PATH):
                shutil.copyfile(QTABLE_PATH, QTABLE_PATH + ".bak")
            if bot.q.games % REPORT_EVERY == 0 and window_scores:
                selections = sum(bot.mode_counts.values()) - sum(last_counts.values())
                dist = " ".join(
                    f"{m}:{(bot.mode_counts[m] - last_counts.get(m, 0)) / max(selections, 1):.0%}"
                    for m in MODES
                )
                print(
                    f"gra {bot.q.games:6d} | "
                    f"śr. score {sum(window_scores) / len(window_scores):5.2f} | "
                    f"śr. miejsce {sum(window_places) / len(window_places):4.1f} | "
                    f"wygrane {sum(window_wins)}/{len(window_wins)} | "
                    f"eps {bot.q.epsilon:.3f} | "
                    f"stany {bot.q.states_seen():4d} | {dist}",
                    flush=True,
                )
                last_counts = dict(bot.mode_counts)
    except KeyboardInterrupt:
        print("Przerwano - zapisuję tabelę.", flush=True)

    bot.q.save()
    print(
        f"Koniec: {bot.q.games} gier, {bot.q.states_seen()} stanów, "
        f"tabela w {QTABLE_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    main()
