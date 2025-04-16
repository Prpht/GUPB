import heapq

MATRIX_STR = """========================
=####.##=C...====....===
==#A...#==....====..=@@=
==.S....==...@==......@=
==#....#===..@@@.=.....=
=##....#====..@..#.#...=
=####.##====......M#=..=
==.....=====.....#.....=
==.###.@.#.==..#.#.#...=
===#.#....@==....#.#...=
=....#...@@.......===..=
=###..B...@.=...====.=.=
=#...##.##..===...==...=
=#...#==.#.===........#=
=#..S#=.....==........@=
=#...#==...===##.###...=
=#.###=..#..==#....#==.=
=....=.......=#BA...====
==..==....@........#====
==.....@.@#@..##.###====
=====..#@@#....M..======
=.....@###....##.#======
=C====@@....=.....======
========================"""


class PathFinder:

    def __init__(self):
        """Initialize the PathFinder with x as column and y as row."""
        self.matrix = self.parse_matrix(MATRIX_STR)
        self.directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]  # Up, Down, Left, Right (dx, dy)
        self.moves = ["UP", "DOWN", "LEFT", "RIGHT"]
        self.hash_map = self.generate_hash_map()  # Precompute hash map
        self.letter_positions = self.find_letters_positions()  # Precompute letter positions

    @staticmethod
    def parse_matrix(matrix_str):
        """Convert the textual representation into a 2D matrix."""
        return [list(row) for row in matrix_str.strip().split("\n")]

    def is_valid_move(self, x, y):
        """Check if (x, y) is a valid move (column, row)."""
        if 0 <= y < len(self.matrix):
            row = self.matrix[y]
            if 0 <= x < len(row):
                return row[x] not in ('=', '#')
        return False

    def compute_distances_and_moves(self, start):
        """Compute shortest distance and initial move from 'start' (x, y) to all valid points."""
        distances = {}
        initial_moves = {}
        heap = [(0, start, None)]  # (distance, (x, y), initial_move)
        visited = set()

        while heap:
            current_distance, (current_x, current_y), initial_move = heapq.heappop(heap)

            if (current_x, current_y) in visited:
                continue

            visited.add((current_x, current_y))
            distances[(current_x, current_y)] = current_distance

            if initial_move is not None:
                initial_moves[(current_x, current_y)] = initial_move

            for i, (dx, dy) in enumerate(self.directions):
                next_x, next_y = current_x + dx, current_y + dy
                if self.is_valid_move(next_x, next_y) and (next_x, next_y) not in visited:
                    next_move = self.moves[i] if initial_move is None else initial_move
                    heapq.heappush(heap, (current_distance + 1, (next_x, next_y), next_move))

        return distances, initial_moves

    def generate_hash_map(self):
        """Generate hash map for all valid (x,y) to (dx,dy) with distance and first move."""
        hash_map = {}
        for y in range(len(self.matrix)):
            row = self.matrix[y]
            for x in range(len(row)):
                if self.is_valid_move(x, y):
                    distances, initial_moves = self.compute_distances_and_moves((x, y))
                    for (dx, dy) in distances:
                        if (dx, dy) == (x, y):
                            hash_map[(x, y, dx, dy)] = (0, "STAY")
                        elif (dx, dy) in initial_moves:
                            hash_map[(x, y, dx, dy)] = (distances[(dx, dy)], initial_moves[(dx, dy)])
        return hash_map

    def find_letters_positions(self, blacklisted=[]):
        """Find positions of letters, stored as (x, y) = (column, row)."""
        letter_positions = {}
        for y, row in enumerate(self.matrix):
            for x, char in enumerate(row):
                if char.isalpha() and (char not in blacklisted):
                    if char not in letter_positions:
                        letter_positions[char] = []
                    letter_positions[char].append((x, y))
        return letter_positions

    def letters_position(self, Xx, Xy, blacklisted=[]):
        """Get distances to all letters from (Xx, Xy)."""
        if not self.is_valid_move(Xx, Xy):
            return "Invalid starting position!"
        result = []
        for letter, positions in self.letter_positions.items():
            if letter in blacklisted:
                continue
            for (x, y) in positions:
                key = (Xx, Xy, x, y)
                if key in self.hash_map:
                    distance, move = self.hash_map[key]
                    result.append((x, y, distance, letter))
        return sorted(result, key=lambda x: x[2])

    def shortest_path(self, Xx, Xy, Yx, Yy):
        key = (Xx, Xy, Yx, Yy)
        return self.hash_map.get(key, None)

    def validate_hash_map_for_target(self, target_x, target_y):
        """Validate hash_map entries for paths to (target_x, target_y)."""
        if not self.is_valid_move(target_x, target_y):
            print(f"Target ({target_x}, {target_y}) is invalid.")
            return False
        errors = []
        for y in range(len(self.matrix)):
            row = self.matrix[y]
            for x in range(len(row)):
                if not self.is_valid_move(x, y) or (x == target_x and y == target_y):
                    continue
                distances, _ = self.compute_distances_and_moves((x, y))
                if (target_x, target_y) in distances:
                    key = (x, y, target_x, target_y)
                    if key not in self.hash_map:
                        errors.append((x, y))
        if errors:
            print(f"Found {len(errors)} missing entries for target ({target_x}, {target_y}).")
            return False
        print(f"All entries for target ({target_x}, {target_y}) are valid.")
        return True
