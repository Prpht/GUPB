class PriorityQueue:
    def __init__(self):
        self.heap = []   # List of entries, each is [key, vertex]
        self.pos = {}    # dictionary: vertex -> index in heap

    def push(self, key, vertex):
        # If already present, decrease the key if new key is better
        if vertex in self.pos:
            self.decrease_key(vertex, key)
        else:
            entry = [key, vertex]
            self.heap.append(entry)
            index = len(self.heap) - 1
            self.pos[vertex] = index
            self._siftup(index)

    def pop(self):
        if not self.heap:
            return None, None
        top = self.heap[0]
        last = self.heap.pop()
        if self.heap:
            self.heap[0] = last
            self.pos[last[1]] = 0
            self._siftdown(0)
        del self.pos[top[1]]
        return tuple(top)  # returns (key, vertex)

    def peek(self):
        return self.heap[0] if self.heap else None

    def decrease_key(self, vertex, new_key):
        """Decrease the key for a given vertex."""
        i = self.pos.get(vertex)
        if i is not None and new_key < self.heap[i][0]:
            self.heap[i][0] = new_key
            self._siftup(i)

    # Helper functions for maintaining the heap property.
    def _siftup(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self.heap[i][0] < self.heap[parent][0]:
                self.heap[i], self.heap[parent] = self.heap[parent], self.heap[i]
                self.pos[self.heap[i][1]] = i
                self.pos[self.heap[parent][1]] = parent
                i = parent
            else:
                break

    def _siftdown(self, i):
        n = len(self.heap)
        while True:
            left = 2 * i + 1
            right = 2 * i + 2
            smallest = i
            if left < n and self.heap[left][0] < self.heap[smallest][0]:
                smallest = left
            if right < n and self.heap[right][0] < self.heap[smallest][0]:
                smallest = right
            if smallest != i:
                self.heap[i], self.heap[smallest] = self.heap[smallest], self.heap[i]
                self.pos[self.heap[i][1]] = i
                self.pos[self.heap[smallest][1]] = smallest
                i = smallest
            else:
                break


class LPAFinder:
    def __init__(self, width: int, height: int):
        """
        Initialize the grid with dimensions (width x height).
        By default, every cell has cost 1 (passable).
        The maze is represented as a 2D grid (list of lists) in self.matrix.
        """
        self.width = width
        self.height = height

        # LPA* specific variables:
        self.INF = float('inf')
        # For each cell, keep the best cost found so far (g) and one-step lookahead (rhs)
        self.g = {}    # g(s) for each cell s
        self.rhs = {}  # rhs(s) for each cell s

        self.U = PriorityQueue()    # Use the custom priority queue
        self.s_start = None  # start cell (x, y)
        self.s_goal = None   # goal cell (x, y)

        self.matrix = [[self.INF if i == 0 or j == 0 or i == self.width - 1 or j == self.height - 1 else 1 for i in range(width)] for j in range(height)]

    ### --- Print matrix --- ###

    def print_matrix(self):
        """Print the current state of the matrix."""
        for row in self.matrix:
            print("".join(str("#" if cell == self.INF else cell) for cell in row))
        print()

    ### --- Heuristic and Key Functions --- ###

    def _heuristic(self, s):
        if self.s_goal is None:
            return 0
        """Use Manhattan distance from cell s to s_goal as the heuristic."""
        return abs(s[0] - self.s_goal[0]) + abs(s[1] - self.s_goal[1])

    def _key(self, s):
        """
        The key for a cell s is a tuple:
          (min(g(s), rhs(s)) + heuristic(s),  min(g(s), rhs(s)) )
        """
        g_val = self.g.get(s, self.INF)
        rhs_val = self.rhs.get(s, self.INF)
        min_val = min(g_val, rhs_val)
        return (min_val + self._heuristic(s), min_val)

    ### --- Neighbors and Cost Helper Functions --- ###

    def _get_neighbors(self, s):
        """Return all valid neighbors (up, down, left, right) for cell s."""
        x, y = s
        neighbors = []
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height and self.matrix[ny][nx] != self.INF:
                neighbors.append((nx, ny))
        return neighbors

    def _cost(self, u, v):
        """
        The cost of moving from cell u to v is defined as the cost of the
        destination cell v, i.e. self.matrix[v[1]][v[0]].
        """
        return self.matrix[v[1]][v[0]]

    ### --- LPA* Initialization and Update Methods --- ###

    def _initialize(self):
        """
        (Re)initialize LPA* state for all grid cells.
        In a fresh run, every cell gets g = infinity and rhs = infinity.
        For the starting cell, rhs(s_start) is set to 0.
        The priority queue U is cleared and s_start pushed.
        """
        self.g = {}
        self.rhs = {}
        for y in range(self.height):
            for x in range(self.width):
                self.g[(x, y)] = self.INF
                self.rhs[(x, y)] = self.INF
        # For the start, set rhs = 0
        self.rhs[self.s_start] = 0
        self.U = PriorityQueue()
        self.U.push(self._key(self.s_start), self.s_start)

    def _ensure_cell_exists(self, cell):
        if cell not in self.g:
            self.g[cell] = self.INF
        if cell not in self.rhs:
            self.rhs[cell] = self.INF

    def _update_vertex(self, u):
        """
        Update a vertex u (a cell in the grid). If u is not the start,
        its rhs value is updated using:
            rhs(u) = min_{s in pred(u)} [g(s) + cost(s, u)]
        Then, if u is not locally consistent (g(u) != rhs(u)), u is added to the queue.
        """
        self._ensure_cell_exists(u)
        if u != self.s_start:
            min_val = self.INF
            for s in self._get_neighbors(u):
                self._ensure_cell_exists(s)
                tentative = self.g[s] + self._cost(s, u)
                if tentative < min_val:
                    min_val = tentative
            self.rhs[u] = min_val

        # Only update if inconsistent
        if self.g[u] != self.rhs[u]:
            if u in self.U.pos:
                self.U.decrease_key(u, self._key(u))
            else:
                self.U.push(self._key(u), u)

    def _compute_shortest_path(self, max_iterations=None):
        """
        The core loop of LPA*. Remove inconsistent vertices from U and update them,
        until s_goal is locally consistent AND the best key in U is not less than the key of s_goal.

        An optional max_iterations parameter serves as a safeguard to prevent infinite loops.
        """
        if max_iterations is None:
            max_iterations = self.width * self.height
        iterations = 0
        while self.U.peek() and (self.U.peek()[0] < self._key(self.s_goal) or self.rhs[self.s_goal] != self.g[self.s_goal]) and iterations < max_iterations:
            iterations += 1
            k_old, u = self.U.pop()
            if self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for s in self._get_neighbors(u):
                    self._update_vertex(s)
            else:
                self.g[u] = self.INF
                self._update_vertex(u)
                for s in self._get_neighbors(u):
                    self._update_vertex(s)

        ### --- Path Reconstruction --- ###

    def _reconstruct_path(self):
        """
        Reconstruct the path from s_start to s_goal using computed g-values.
        For each cell v on the path, we choose the neighbor u that minimizes:
            | g(v) - [g(u) + cost(u, v)] |
        and then we reconstruct the path backwards (from s_goal to s_start)
        and reverse it. Returns a list of cells representing the path, or None if no valid path is found.
        """
        # If the goal is unreachable, return None.
        if self.g.get(self.s_goal, self.INF) == self.INF:
            return None

        path = [self.s_goal]
        current = self.s_goal

        while current != self.s_start:
            best = None
            best_diff = self.INF
            # Check all neighbors of current for the one that best “explains” its cost.
            for neighbor in self._get_neighbors(current):
                # Only consider neighbor if it is reachable.
                if self.g.get(neighbor, self.INF) != self.INF:
                    # Calculate how far off the consistency condition is.
                    diff = abs(self.g[current] - (self.g[neighbor] + self._cost(neighbor, current)))
                    if diff < best_diff:
                        best_diff = diff
                        best = neighbor

            # If no candidate is found, reconstruction fails.
            if best is None:
                return None

            path.append(best)
            current = best

            # Safeguard: if the path length exceeds total cells, something is wrong.
            if len(path) > self.width * self.height:
                return None

        path.reverse()
        return path

    ### --- Public Interface Methods --- ###

    def shortest_path(self, Xx: int, Xy: int, Yx: int, Yy: int) -> Tuple[float, str]:
        """
        Compute the shortest path from (Xx, Xy) [start] to (Yx, Yy) [goal]
        using the dynamic LPA* algorithm.

        This method keeps the same signature as before.
        Returns a tuple: (total_cost, first_move) where first_move is one of:
        "UP", "DOWN", "LEFT", "RIGHT", or "STAY".
        If no path is found, (None is returned.)
        If start == goal: (0, "STAY") is returned
        """
        if self.matrix[Xy][Xx] == self.INF or self.matrix[Yy][Yx] == self.INF:
            return None
        new_start = (Xx, Xy)
        new_goal = (Yx, Yy)
        if new_start == new_goal:
            return (0, "STAY")
        # print("shortest_path", new_start, new_goal)
        if self.s_start != new_start or self.s_goal != new_goal:
            self.s_start = new_start
            self.s_goal = new_goal
            self._initialize()
        self._compute_shortest_path()
        if self.g[self.s_goal] == self.INF:
            return None
        path = self._reconstruct_path()
        if not path or len(path) < 2:
            return None
        dx = path[1][0] - self.s_start[0]
        dy = path[1][1] - self.s_start[1]
        if dx == 0 and dy == -1:
            direction = "UP"
        elif dx == 0 and dy == 1:
            direction = "DOWN"
        elif dx == -1 and dy == 0:
            direction = "LEFT"
        elif dx == 1 and dy == 0:
            direction = "RIGHT"
        else:
            direction = "STAY"
        return (self.g[self.s_goal], direction)

    def update_cell(self, x: int, y: int, new_value: float) -> None:
        """
        Update the cost of cell (x, y) to new_value.
        The semantics are:
            • 1  → passable with low cost.
            • >1 → passable but with a higher cost.
            • self.INF → wall.

        After updating, only affected vertices (the cell itself and its neighbors)
        are re-evaluated via update_vertex(), and then compute_shortest_path() is called
        so that only the necessary parts of the search tree are repaired.
        """
        if self.matrix[y][x] == new_value:
            return
        self.matrix[y][x] = new_value

        affected = {(x, y)}
        for neighbor in self._get_neighbors((x, y)):
            affected.add(neighbor)

        for u in affected:
            self._ensure_cell_exists(u)  # Lazy initialization of the cell values.
            self._update_vertex(u)

        self._compute_shortest_path()


    def distances_from_start(self, x: int, y: int) -> Dict[Tuple[int, int], float]:
        """
        Compute the shortest distances from the given start node (X, Y)
        to every reachable cell in the grid.

        This method reinitializes the LPA* state using (X, Y) as the start,
        then processes the entire queue (instead of stopping with a specific goal)
        so that every achievable node in the grid is relaxed.

        Returns a dictionary mapping each cell (x, y) that is reachable (g < INF)
        to its computed distance (g-value).
        """
        # Set the given start.
        self.s_start = (x, y)

        # Reinitialize g and rhs for every cell.
        self.g = {}
        self.rhs = {}
        for y in range(self.height):
            for x in range(self.width):
                self.g[(x, y)] = self.INF
                self.rhs[(x, y)] = self.INF
        # The start node has a rhs of 0.
        self.rhs[self.s_start] = 0

        # Initialize the priority queue.
        # (You can use your custom PriorityQueue with decrease-key, or the lazy one.)
        # Here we assume that self.U is a PriorityQueue that supports push/pop.
        self.U = PriorityQueue()
        self.U.push(self._key(self.s_start), self.s_start)

        # Process until the queue is empty.
        while self.U.peek() is not None:
            k_old, u = self.U.pop()
            if self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for s in self._get_neighbors(u):
                    self._update_vertex(s)
            else:
                self.g[u] = self.INF
                self._update_vertex(u)
                for s in self._get_neighbors(u):
                    self._update_vertex(s)

        # Build up the dictionary of reachable distances.
        reachable = {}
        for y in range(self.height):
            for x in range(self.width):
                cell = (x, y)
                if self.g[cell] < self.INF:
                    reachable[cell] = self.g[cell]
        return reachable
