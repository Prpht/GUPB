from itertools import repeat
import random
from typing import Iterator

import networkx as nx
import perlin_noise
import scipy.stats as scp_stats
from tqdm import tqdm

ArenaDefinition = list[list[str]]

DEFAULT_WIDTH = 24
DEFAULT_HEIGHT = 24
MIN_SIZE = 20
MAX_SIZE = 40
PERLIN_NOISE_OCTAVES = 4
REQUIRED_AREA_COEFFICIENT = 0.4
WEAPONS_PER_BUILDING = 2
BUILDINGS_PER_ARENA = 10
MAX_BUILDING_SIZE = 10

WEAPONS = ['S', 'A', 'B', 'M']


def mountain_probability(intensity: float) -> float:
    return scp_stats.logistic.cdf(intensity, loc=0.30, scale=0.05)


def sea_probability(intensity: float) -> float:
    return 1.0 - scp_stats.logistic.cdf(intensity, loc=-0.05, scale=0.05)


def empty_arena(width: int, height: int) -> ArenaDefinition:
    return [['='] * width for _ in range(height)]


def perlin_landscape_arena(width: int, height: int) -> ArenaDefinition:
    arena = empty_arena(width, height)
    perlin_width, perlin_height = width - 2, height - 2
    noise = perlin_noise.PerlinNoise(octaves=PERLIN_NOISE_OCTAVES)
    noise_picture = [
        [noise([i / perlin_width, j / perlin_height]) for j in range(perlin_width)]
        for i in range(perlin_height)
    ]
    for i in range(perlin_height):
        for j in range(perlin_width):
            coin = random.random()
            coin -= mountain_probability(noise_picture[i][j])
            if coin < 0.0:
                arena[i + 1][j + 1] = '#'
                continue
            coin -= sea_probability(noise_picture[i][j])
            if coin < 0.0:
                arena[i + 1][j + 1] = '='
                continue
            arena[i + 1][j + 1] = '.'
    return arena


def arena_dimensions(arena: ArenaDefinition) -> tuple[int, int]:
    width, height = len(arena[0]), len(arena)
    return width, height


def add_buildings(arena: ArenaDefinition) -> None:
    width, height = arena_dimensions(arena)
    for _ in range(BUILDINGS_PER_ARENA):
        building_width, building_height = random.randint(3, MAX_BUILDING_SIZE), random.randint(3, MAX_BUILDING_SIZE)
        building_j = random.randint(1, width - building_width - 1)
        building_i = random.randint(1, height - building_height - 1)
        for i in range(building_height):
            for j in range(building_width):
                arena[building_i + i][building_j + j] = '#'
        for i in range(building_height - 2):
            for j in range(building_width - 2):
                arena[building_i + i + 1][building_j + j + 1] = '.'

        doors_no = random.randint(2, 4)
        locations = ['top', 'bottom', 'left', 'right']
        door_locations = random.sample(locations, doors_no)
        if 'top' in door_locations:
            door_shift = random.randint(1, building_width - 2)
            arena[building_i][building_j + door_shift] = '.'
        if 'bottom' in door_locations:
            door_shift = random.randint(1, building_width - 2)
            arena[building_i + building_height - 1][building_j + door_shift] = '.'
        if 'left' in door_locations:
            door_shift = random.randint(1, building_height - 2)
            arena[building_i + door_shift][building_j] = '.'
        if 'right' in door_locations:
            door_shift = random.randint(1, building_height - 2)
            arena[building_i + door_shift][building_j + building_width - 1] = '.'

        treasure_no = random.randint(1, min(WEAPONS_PER_BUILDING, (building_width - 2) * (building_height - 2)))
        for _ in range(treasure_no):
            treasure_i, treasure_j = random.randint(1, building_height - 2), random.randint(1, building_width - 2)
            treasure_type = random.choice(WEAPONS)
            arena[building_i + treasure_i][building_j + treasure_j] = treasure_type


def is_passable(field: str) -> bool:
    return field == '.' or field in WEAPONS


def create_arena_graph(arena: ArenaDefinition) -> nx.Graph:
    def add_passable_edge(i_target: int, j_target: int):
        if 0 <= i_target < height and 0 <= j_target < width and is_passable(arena[i_target][j_target]):
            arena_graph.add_edge((i, j), (i_target, j_target))

    arena_graph = nx.Graph()
    width, height = arena_dimensions(arena)
    for i in range(height):
        for j in range(width):
            if is_passable(arena[i][j]):
                arena_graph.add_node((i, j))
                add_passable_edge(i + 1, j)
                add_passable_edge(i - 1, j)
                add_passable_edge(i, j + 1)
                add_passable_edge(i, j - 1)
    return arena_graph


def remove_disconnected_islands(arena: ArenaDefinition) -> int:
    arena_graph = create_arena_graph(arena)
    connected_components = [c for c in sorted(nx.connected_components(arena_graph), key=len, reverse=True)]
    for component in connected_components[1:]:
        component_size = len(component)
        # noinspection PyTypeChecker
        for i, j in component:
            if component_size > 5:
                arena[i][j] = '='
            else:
                arena[i][j] = '#'
    return len(connected_components[0])


def generate_arena(width: int, height: int) -> ArenaDefinition:
    required_area = int(width * height * REQUIRED_AREA_COEFFICIENT)
    while True:
        arena = perlin_landscape_arena(width, height)
        add_buildings(arena)
        playable_area = remove_disconnected_islands(arena)
        if playable_area > required_area:
            break
    return arena


def save_arena(arena: ArenaDefinition, file_name: str) -> None:
    def write_arena() -> None:
        with open(file_path, 'w') as file:
            for line in arena:
                for character in line:
                    file.write(character)
                file.write('\n')

    def remove_last_new_line() -> None:
        with open(file_path, 'r+') as file:
            content = file.read()
            content = content.rstrip('\n')
            file.seek(0)
            file.write(content)
            file.truncate()

    file_path = f"./resources/arenas/{file_name}.gupb"
    write_arena()
    remove_last_new_line()


def generate_arenas(
        how_many: int,
        size_generator: Iterator[tuple[int, int]] = repeat((DEFAULT_WIDTH, DEFAULT_HEIGHT))
) -> list[str]:
    arena_names = [f"generated_{i}" for i in range(how_many)]
    for name in tqdm(arena_names, desc="Generating arenas"):
        arena = generate_arena(*next(size_generator))
        save_arena(arena, name)
    return arena_names


def random_size_generator() -> Iterator[tuple[int, int]]:
    while True:
        size = random.randint(MIN_SIZE, MAX_SIZE)
        yield size, size


def main() -> None:
    generate_arenas(10)


if __name__ == '__main__':
    main()
