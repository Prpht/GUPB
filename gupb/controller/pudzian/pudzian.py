import atexit
import json
import random
from datetime import datetime
from pathlib import Path

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates


# Prosty bot uczacy sie tablicowo.
# Nie jest to duzy model neuronowy, tylko mala tablica Q,
# ktora pamieta, co zwykle dzialalo w danym stanie.
LEARNING_RATE = 0.25
DISCOUNT_FACTOR = 0.85
EXPLORATION_RATE = 0.15

# Zestaw akcji, z ktorych bot bedzie wybieral.
# Zostawiamy kilka podstawowych ruchow, zeby uczenie bylo proste.
TRAINING_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING,
]


class Pudzian(controller.Controller):
    def __init__(self, bot_name: str) -> None:
        self.bot_name = bot_name

        # Te pola sa tylko do podgladu i zapisu stanu.
        self.current_game_no: int = 0
        self.current_arena: str | None = None
        self.last_score: int = 0
        self.total_score: int = 0
        self.games_played: int = 0
        self.best_score: int = 0

        # Tablica Q: stan -> {akcja -> wartosc}
        # Stan zapisujemy jako napis, bo tak latwo zapisac go do JSON.
        self.q_table: dict[str, dict[str, float]] = {}

        # Tutaj trzymamy cala trase jednej gry.
        # Po zakonczeniu gry zrobimy z niej aktualizacje Q-learningu.
        self.episode_memory: list[tuple[str, str]] = []

        # Pliki do zapisu stanu uczenia.
        self.results_dir: Path = Path(__file__).resolve().parent / "results"
        self.latest_model_path: Path = self.results_dir / "latest_model.json"
        self.best_model_path: Path = self.results_dir / "best_model.json"
        self.final_results_path: Path = self.results_dir / "final_results.jsonl"

        self._final_state_saved = False
        self._load_previous_state()
        atexit.register(self._save_final_training_state)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Pudzian):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Zamieniamy obserwacje na maly opis stanu.
        # To jest baza dla calego uczenia.
        state_key = self._build_state_key(knowledge)

        # Najpierw probujemy wybrac akcje wedlug Q-table,
        # ale czasem robimy losowy ruch, zeby dalej eksplorowac.
        chosen_action = self._select_action(state_key, knowledge)

        # Pamietamy, co zrobilismy w tym kroku.
        # Pozniej wykorzystamy to do uczenia po zakonczeniu gry.
        self.episode_memory.append((state_key, chosen_action.name))
        return chosen_action

    def _select_action(self, state_key: str, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Eksploracja: czasem wybieramy losowa akcje, zeby bot
        # nie utknal na jednym schemacie zachowania.
        if random.random() < EXPLORATION_RATE:
            return random.choice(TRAINING_ACTIONS)

        q_values = self._get_q_values(state_key)
        best_value = max(q_values.values())

        # Na poczatku wszystkie wartosci sa rowne zero.
        # Wtedy korzystamy z prostej heurystyki, zeby start byl sensowny.
        if best_value == 0.0:
            return self._heuristic_action(knowledge)

        best_actions = [
            getattr(characters.Action, action_name)
            for action_name, value in q_values.items()
            if value == best_value
        ]
        return random.choice(best_actions)

    def _heuristic_action(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # To jest prosty plan awaryjny.
        # Gdy bot niczego jeszcze nie wie, gra "rozsadnie".
        current_tile = knowledge.visible_tiles.get(knowledge.position)
        if current_tile is None or current_tile.character is None:
            return characters.Action.TURN_RIGHT

        own_facing = current_tile.character.facing
        front_position = knowledge.position + own_facing.value
        front_tile = knowledge.visible_tiles.get(front_position)

        # Jesli wrog stoi przed nami, atakujemy od razu.
        if self._has_enemy(front_tile, self.bot_name):
            return characters.Action.ATTACK

        # Jesli wrog jest obok, probujemy sie do niego obrocic.
        adjacent_enemy = self._find_adjacent_enemy(knowledge)
        if adjacent_enemy is not None:
            return self._action_towards(knowledge.position, adjacent_enemy, own_facing)

        # Najpierw mikstury, potem lootr.
        potion_target = self._nearest_target(knowledge, lambda tile: tile.consumable is not None)
        if potion_target is not None:
            return self._move_towards(knowledge, potion_target, own_facing)

        loot_target = self._nearest_target(knowledge, lambda tile: tile.loot is not None)
        if loot_target is not None:
            return self._move_towards(knowledge, loot_target, own_facing)

        # Ostateczny fallback: idz do przodu, a jak sie nie da,
        # to skrecaj w prawo i szukaj nowej sciezki.
        if self._is_passable(front_tile):
            return characters.Action.STEP_FORWARD
        return characters.Action.TURN_RIGHT

    @staticmethod
    def _has_enemy(tile, own_name: str) -> bool:
        return tile is not None and tile.character is not None and tile.character.controller_name != own_name

    @staticmethod
    def _is_passable(tile) -> bool:
        if tile is None or tile.character is not None:
            return False
        return tile.type in {"land", "forest", "menhir"}

    def _find_adjacent_enemy(self, knowledge: characters.ChampionKnowledge) -> coordinates.Coords | None:
        # Sprawdzamy cztery sasiednie pola.
        # To pomaga szybko reagowac na wrogow w zasięgu.
        for delta in [
            coordinates.Coords(0, -1),
            coordinates.Coords(1, 0),
            coordinates.Coords(0, 1),
            coordinates.Coords(-1, 0),
        ]:
            candidate = knowledge.position + delta
            if self._has_enemy(knowledge.visible_tiles.get(candidate), self.bot_name):
                return candidate
        return None

    def _nearest_target(self, knowledge: characters.ChampionKnowledge, predicate) -> coordinates.Coords | None:
        # Szukamy najblizszego widocznego celu.
        # Z tego korzystamy przy polowaniu na mikstury i bron.
        best_position = None
        best_distance = None
        for position, tile in knowledge.visible_tiles.items():
            if not predicate(tile):
                continue
            distance = abs(position.x - knowledge.position.x) + abs(position.y - knowledge.position.y)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_position = position
        return best_position

    def _move_towards(
        self,
        knowledge: characters.ChampionKnowledge,
        target: coordinates.Coords,
        facing: characters.Facing,
    ) -> characters.Action:
        # Najpierw wybieramy kierunek, a potem sprawdzamy,
        # czy przypadkiem nie probujemy wejsc w sciane.
        action = self._action_towards(knowledge.position, target, facing)
        if action == characters.Action.STEP_FORWARD:
            forward_tile = knowledge.visible_tiles.get(knowledge.position + facing.value)
            if not self._is_passable(forward_tile):
                return characters.Action.TURN_RIGHT
        return action

    @staticmethod
    def _action_towards(
        position: coordinates.Coords,
        target: coordinates.Coords,
        facing: characters.Facing,
    ) -> characters.Action:
        # Bardzo prosta nawigacja lokalna.
        # Wybieramy os, ktora jest bardziej oddalona.
        dx = target.x - position.x
        dy = target.y - position.y

        if abs(dx) >= abs(dy):
            desired = coordinates.Coords(1, 0) if dx > 0 else coordinates.Coords(-1, 0)
        else:
            desired = coordinates.Coords(0, 1) if dy > 0 else coordinates.Coords(0, -1)

        if desired == facing.value:
            return characters.Action.STEP_FORWARD
        if desired == facing.turn_left().value:
            return characters.Action.TURN_LEFT
        if desired == facing.turn_right().value:
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        # Tu następuje sam "uczący" moment.
        # Po zakonczeniu gry dostajemy wynik i na jego podstawie
        # poprawiamy wszystkie decyzje zapisane w episode_memory.
        self.last_score = score
        self.total_score += score
        self.games_played += 1
        if score > self.best_score:
            self.best_score = score

        self._update_q_table(score)
        self.episode_memory.clear()

    def _update_q_table(self, final_reward: int) -> None:
        # Aktualizacja jest bardzo prosta:
        # zaczynamy od koncowego wyniku i cofamy sie po historii ruchow.
        # Dzieki temu wczesniejsze decyzje dostaja troche mniejsza wage.
        discounted_reward = float(final_reward)
        for state_key, action_name in reversed(self.episode_memory):
            q_values = self._get_q_values(state_key)
            current_value = q_values[action_name]
            q_values[action_name] = current_value + LEARNING_RATE * (discounted_reward - current_value)
            discounted_reward *= DISCOUNT_FACTOR

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        # Reset oznacza start nowej gry.
        # Czyscimy pamiec epizodu, ale tablica Q zostaje.
        self.current_game_no = game_no
        self.current_arena = arena_description.name
        self.episode_memory.clear()

    def _build_state_key(self, knowledge: characters.ChampionKnowledge) -> str:
        # Stan robimy maly i czytelny:
        # - pasek zdrowia,
        # - czy wróg jest z przodu,
        # - czy jest blisko,
        # - czy w ogole widac wroga,
        # - czy widac miksture,
        # - czy widac bron,
        # - czy pole przed nami jest przechodnie.
        current_tile = knowledge.visible_tiles.get(knowledge.position)
        if current_tile is None or current_tile.character is None:
            return "unknown"

        own_facing = current_tile.character.facing
        front_position = knowledge.position + own_facing.value
        front_tile = knowledge.visible_tiles.get(front_position)

        health = current_tile.character.health
        if health <= 2:
            health_bucket = 0
        elif health <= 5:
            health_bucket = 1
        else:
            health_bucket = 2

        enemy_front = int(self._has_enemy(front_tile, self.bot_name))
        enemy_near = int(self._find_adjacent_enemy(knowledge) is not None)
        enemy_visible = int(
            any(self._has_enemy(tile, self.bot_name) for tile in knowledge.visible_tiles.values())
        )
        potion_visible = int(any(tile.consumable is not None for tile in knowledge.visible_tiles.values()))
        loot_visible = int(any(tile.loot is not None for tile in knowledge.visible_tiles.values()))
        front_passable = int(self._is_passable(front_tile))

        return self._state_key((health_bucket, enemy_front, enemy_near, enemy_visible, potion_visible, loot_visible, front_passable))

    @staticmethod
    def _state_key(parts: tuple[int, ...]) -> str:
        # JSON nie lubi krotek jako kluczy, wiec zamieniamy stan na napis.
        return "|".join(str(part) for part in parts)

    def _get_q_values(self, state_key: str) -> dict[str, float]:
        # Jesli widzimy nowy stan, tworzymy dla niego pusta tablice wartosci.
        if state_key not in self.q_table:
            self.q_table[state_key] = {action.name: 0.0 for action in TRAINING_ACTIONS}
        return self.q_table[state_key]

    def _load_previous_state(self) -> None:
        # Najpierw probujemy wczytac latest_model.json,
        # a jesli go nie ma, to best_model.json.
        self.results_dir.mkdir(parents=True, exist_ok=True)

        loaded_state = self._read_json(self.latest_model_path)
        if loaded_state is None:
            loaded_state = self._read_json(self.best_model_path)

        if loaded_state is None:
            return

        self.total_score = int(loaded_state.get("total_score", 0))
        self.games_played = int(loaded_state.get("games_played", 0))
        self.best_score = int(loaded_state.get("best_score", 0))
        self._load_q_table(loaded_state.get("q_table", {}))

    def _load_q_table(self, raw_q_table: object) -> None:
        # Odtwarzamy tablice Q z JSON-a.
        # Każdy stan ma swoje wartosci dla konkretnych akcji.
        if not isinstance(raw_q_table, dict):
            return

        for state_key, action_values in raw_q_table.items():
            if not isinstance(state_key, str) or not isinstance(action_values, dict):
                continue
            self.q_table[state_key] = {}
            for action_name, value in action_values.items():
                if action_name in {action.name for action in TRAINING_ACTIONS}:
                    self.q_table[state_key][action_name] = float(value)

    def _save_final_training_state(self) -> None:
        # Zapis robimy tylko raz, na koncu calego programu.
        # To znaczy: nie zapisujemy po kazdej grze, tylko po calym uruchomieniu.
        if self._final_state_saved or self.games_played <= 0:
            return

        self._final_state_saved = True
        self.results_dir.mkdir(parents=True, exist_ok=True)

        average_score = self.total_score / self.games_played
        full_snapshot = self._build_snapshot(include_q_table=True)
        summary_snapshot = self._build_snapshot(include_q_table=False)
        summary_snapshot["average_score"] = average_score

        # latest_model.json zawiera pelny stan do wznowienia treningu.
        self._write_json(self.latest_model_path, full_snapshot)

        # final_results.jsonl dostaje tylko koncowy wynik danej sesji.
        self._append_json_line(self.final_results_path, summary_snapshot)

        # best_model.json przechowuje najlepsza sesje wedlug total_score.
        self._maybe_update_best_model(full_snapshot)

    def _build_snapshot(self, include_q_table: bool) -> dict:
        snapshot = {
            "bot_name": self.bot_name,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "games_played": self.games_played,
            "total_score": self.total_score,
            "last_score": self.last_score,
            "best_score": self.best_score,
            "last_arena": self.current_arena,
            "last_game_no": self.current_game_no,
        }

        if include_q_table:
            snapshot["q_table"] = self.q_table
        return snapshot

    def _maybe_update_best_model(self, final_state: dict) -> None:
        current_best = self._read_json(self.best_model_path)
        if current_best is None:
            self._write_json(self.best_model_path, final_state)
            return

        current_best_total = float(current_best.get("total_score", float("-inf")))
        new_total = float(final_state.get("total_score", float("-inf")))
        if new_total > current_best_total:
            self._write_json(self.best_model_path, final_state)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(data, dict):
            return data
        return None

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=True, indent=2)

    @staticmethod
    def _append_json_line(path: Path, data: dict) -> None:
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(data, ensure_ascii=True) + "\n")

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PUDZIAN
