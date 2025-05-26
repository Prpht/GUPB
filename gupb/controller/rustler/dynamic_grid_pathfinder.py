from typing import Tuple, Dict, List, Set
from collections import deque
import heapq
import itertools


class PriorityQueue:
    def __init__(self):
        # Each heap entry is of the form [key, count, vertex] where 'count' breaks ties.
        self.heap = []
        self.pos = {}  # Maps vertices to their current valid entry.
        self.counter = itertools.count()  # Unique, ever-increasing counter.
        self.REMOVED = object()  # Sentinel for a removed entry.

    def push(self, key, vertex):
        if vertex in self.pos:
            self.decrease_key(vertex, key)
        else:
            count = next(self.counter)
            entry = [key, count, vertex]
            self.pos[vertex] = entry
            heapq.heappush(self.heap, entry)

    def pop(self) -> Tuple[float, any]:
        while self.heap:
            key, count, vertex = heapq.heappop(self.heap)
            if vertex is not self.REMOVED:
                del self.pos[vertex]
                return key, vertex
        return None, None

    def peek(self):
        # Clean up any removed entries.
        while self.heap and self.heap[0][2] is self.REMOVED:
            heapq.heappop(self.heap)
        if not self.heap:
            return None
        return (self.heap[0][0], self.heap[0][2])

    def decrease_key(self, vertex, new_key):
        if vertex in self.pos:
            entry = self.pos[vertex]
            if new_key < entry[0]:
                # Mark the old entry as removed.
                entry[-1] = self.REMOVED
                count = next(self.counter)
                new_entry = [new_key, count, vertex]
                self.pos[vertex] = new_entry
                heapq.heappush(self.heap, new_entry)

class DynamicGridPathfinder:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.INF = float('inf')
        # Create a matrix with walls on the boundaries and cost 1 inside.
        self.matrix = [
            [self.INF if i == 0 or j == 0 or i == self.width - 1 or j == self.height - 1 else 1
             for i in range(width)]
            for j in range(height)
        ]
        self.s_start = None
        self.s_goal = None

    def print_matrix(self):
        for row in self.matrix:
            print("".join(str("#") if cell == self.INF else str(cell) for cell in row))
        print()

    def _get_neighbors(self, s: Tuple[int, int]):
        """Return 4-connected neighbors that are not walls (i.e. cells with value INF)."""
        x, y = s
        neighbors = []
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height and self.matrix[ny][nx] != self.INF:
                neighbors.append((nx, ny))
        return neighbors

    def _cost(self, u, v):
        # Returns the cost of moving from u to v.
        return self.matrix[v[1]][v[0]]

    def shortest_path(self, Xx: int, Xy: int, Yx: int, Yy: int) -> Tuple[float, str]:
        if self.matrix[Xy][Xx] == self.INF or self.matrix[Yy][Yx] == self.INF:
            return None
        new_start = (Xx, Xy)
        new_goal = (Yx, Yy)
        if new_start == new_goal:
            return (0, "STAY")

        self.s_start = new_start
        self.s_goal = new_goal

        INF = self.INF
        start = self.s_start
        goal = self.s_goal

        dists = {}
        prev = {}
        visited = set()
        pq = PriorityQueue()
        pq.push(0, start)
        dists[start] = 0
        found = False

        while True:
            current_dist, u = pq.pop()
            if u is None:
                break
            if u in visited:
                continue
            visited.add(u)

            if u == goal:
                found = True
                break

            for v in self._get_neighbors(u):
                cost = self._cost(u, v)
                tentative = current_dist + cost
                if v not in dists or tentative < dists[v]:
                    dists[v] = tentative
                    prev[v] = u
                    pq.push(tentative, v)

        if not found or dists.get(goal, INF) == INF:
            return None

        path = []
        current = goal
        while True:
            path.append(current)
            if current == start:
                break
            current = prev.get(current)
            if current is None:
                return None

        path.reverse()
        if len(path) < 2:
            return None

        dx = path[1][0] - path[0][0]
        dy = path[1][1] - path[0][1]
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

        return (dists[goal], direction)


    def update_cell(self, x: int, y: int, new_value: float) -> None:
        if self.matrix[y][x] == new_value:
            return
        self.matrix[y][x] = new_value

    def shortest_paths(self, Xx: int, Xy: int, destinations: List[Tuple[int, int]]) -> Tuple[int, List[Tuple[int, int]]]:
        """
        Compute the shortest path distances from a fixed starting cell (Xx, Xy)
        to multiple destination cells, and return only those destination coordinates
        (Yx, Yy) whose travel cost from the start is minimal.

        Blocked cells (determined by self.matrix[y][x] == self.INF) are ignored.
        If the start is blocked or no destination is reachable, an empty list is returned.
        """
        start = (Xx, Xy)
        # If the starting cell is blocked, return an empty list.
        if self.matrix[Xy][Xx] == self.INF:
            return []
        
        # Filter out any blocked destination cells.
        valid_destinations = {dest for dest in destinations 
                            if 0 <= dest[1] < self.height and 0 <= dest[0] < self.width 
                            and self.matrix[dest[1]][dest[0]] != self.INF}

        if not valid_destinations:
            return None, []

        # Dictionary to store the distance from the start to each cell.
        dists: dict[Tuple[int, int], float] = {start: 0}
        visited = set()
        
        # Priority queue is assumed to have push(priority, item) and pop() methods (returning (priority, item)).
        pq = PriorityQueue()
        pq.push(0, start)
        
        # Optional: exit early when all valid destinations have been reached.
        found_count = 0
        total_targets = len(valid_destinations)
        
        # Run Dijkstra's algorithm until the queue is empty or all valid destinations are reached.
        while True:
            current_dist, current = pq.pop()
            if current is None:
                break  # Queue is empty.
            if current in visited:
                continue
            
            visited.add(current)
            
            if current in valid_destinations:
                found_count += 1
                if found_count == total_targets:
                    break
            
            for neighbor in self._get_neighbors(current):
                cost = self._cost(current, neighbor)
                new_distance = current_dist + cost
                if new_distance < dists.get(neighbor, self.INF):
                    dists[neighbor] = new_distance
                    pq.push(new_distance, neighbor)
        
        # Among the given destination queries, find those with the minimal travel cost.
        best_cost = self.INF
        best_destinations: List[Tuple[int, int]] = []
        for dest in valid_destinations:
            # Skip a destination if it's blocked.
            if self.matrix[dest[1]][dest[0]] == self.INF:
                continue
            cost = dists.get(dest, self.INF)
            if cost < best_cost:
                best_cost = cost
                best_destinations = [dest]
            elif cost == best_cost:
                best_destinations.append(dest)
        
        return best_cost, best_destinations

    def distances_from_start(self, x: int, y: int, key_only: bool, max_dist: int) -> Dict[Tuple[int, int], float]:
        start = (x, y)

        if key_only:
            visited = {start}
            queue = deque([start])
            while queue:
                u = queue.popleft()
                for v in self._get_neighbors(u):
                    if v not in visited:
                        visited.add(v)
                        queue.append(v)
            return {cell: 0.0 for cell in visited}
        else:
            dists = {}
            pq = PriorityQueue()
            pq.push(0, start)
            dists[start] = 0
            visited = set()

            while True:
                current_dist, u = pq.pop()
                if u is None:
                    break
                if u in visited:
                    continue
                visited.add(u)

                if current_dist >= max_dist:
                    continue

                for v in self._get_neighbors(u):
                    cost = self._cost(u, v)
                    tentative = current_dist + cost
                    if v not in dists or tentative < dists[v]:
                        dists[v] = tentative
                        pq.push(tentative, v)

            return {cell: dists[cell] for cell in dists if dists[cell] < max_dist}

    # ----- New methods for safe cell clearance and candidate selection -----

    def is_safe(self, s: Tuple[int,int]) -> bool:
        """
        In this grid, a safe cell is one that is not a wall (INF) and not misted.
        (A misted cell has value 8.)
        """
        x, y = s
        return self.matrix[y][x] != 8 and self.matrix[y][x] != self.INF

    def _get_safe_neighbors(self, s: Tuple[int,int]) -> List:
        """
        Returns 4-connected neighbors of cell s that are safe (i.e. not misted and not walls).
        """
        return [n for n in self._get_neighbors(s) if self.is_safe(n)]

    def get_safe_component(self, safe_start: Tuple[int, int]) -> Set:
        """
        From a given safe starting cell, retrieve the connected component of safe cells.
        A cell is considered safe if its value is not 8 (misted) and not a wall (INF).
        """
        comp = set()
        dq = deque([safe_start])
        comp.add(safe_start)
        while dq:
            cell = dq.popleft()
            for neighbor in self._get_safe_neighbors(cell):
                if neighbor not in comp:
                    comp.add(neighbor)
                    dq.append(neighbor)
        return comp

    def get_max_clearance_cell_with_clearance(self, safe_start: Tuple[int, int]) -> Tuple[Tuple[int,int], float]:
        # Initialize cache if not present
        if not hasattr(self, 'component_cache'):
            self.component_cache = {}  # Maps component_id to (safe_region, mist_boundary, wall_boundary, clearance, best_cell, best_clearance)
            self.cell_to_component = {}  # Maps (x, y) to component_id
            self.component_counter = 0  # Unique ID for each component

        # Check if safe_start is in a known component
        component_id = self.cell_to_component.get(safe_start)
        if component_id is not None and component_id in self.component_cache:
            safe_region, mist_boundary, wall_boundary, clearance, best_cell, best_clearance = self.component_cache[component_id]
            # print(f"Cache hit for component {component_id}, size: {len(safe_region)}, returning {best_cell}, {best_clearance}")
            return best_cell, best_clearance

        # Compute safe component and boundaries
        safe_region = set()
        mist_boundary = set()
        wall_boundary = set()
        dq = deque([safe_start])
        safe_region.add(safe_start)
        visited = {safe_start}
        
        while dq:
            x, y = dq.popleft()
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                neighbor = (nx, ny)
                neighbor_value = self.matrix[ny][nx]
                if neighbor_value == self.INF:
                    wall_boundary.add((x, y))
                elif neighbor_value == 8:
                    mist_boundary.add((x, y))
                elif neighbor not in visited and neighbor_value != 8 and neighbor_value != self.INF:
                    visited.add(neighbor)
                    safe_region.add(neighbor)
                    dq.append(neighbor)
        
        # Assign component ID
        component_id = self.component_counter
        self.component_counter += 1
        for cell in safe_region:
            self.cell_to_component[cell] = component_id
        
        # print(f"New component {component_id}, size: {len(safe_region)}, mist boundary: {len(mist_boundary)}")

        # Initialize clearance array only for safe_region cells
        clearance = {}  # Sparse dictionary for safe_region only
        for cell in safe_region:
            clearance[cell] = -1
        
        # Handle no mist boundary
        if not mist_boundary:
            if not wall_boundary:
                # print("No mist or wall boundary, caching and returning safe_start")
                self.component_cache[component_id] = (safe_region, mist_boundary, wall_boundary, clearance, safe_start, float('inf'))
                return safe_start, float('inf')
            
            # BFS from wall boundary
            dq = deque(wall_boundary)
            for x, y in wall_boundary:
                clearance[(x, y)] = 0
            
            best_clearance = 0
            best_cell = safe_start
            max_possible = max(self.width, self.height)  # Early termination bound
            while dq:
                x, y = dq.popleft()
                curr_clearance = clearance[(x, y)]
                if curr_clearance > best_clearance:
                    best_clearance = curr_clearance
                    best_cell = (x, y)
                if curr_clearance >= max_possible:
                    break  # No cell can have higher clearance
                for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                    nx, ny = x + dx, y + dy
                    neighbor = (nx, ny)
                    if neighbor in safe_region and clearance[neighbor] == -1:
                        clearance[neighbor] = curr_clearance + 1
                        dq.append(neighbor)
            
            # print(f"Best cell (from walls): {best_cell}, Clearance: {best_clearance}")
            self.component_cache[component_id] = (safe_region, mist_boundary, wall_boundary, clearance, best_cell, best_clearance)
            return best_cell, best_clearance
        
        # BFS from mist boundary
        dq = deque(mist_boundary)
        for x, y in mist_boundary:
            clearance[(x, y)] = 0
        
        best_clearance = 0
        best_cell = safe_start
        max_possible = max(self.width, self.height)
        while dq:
            x, y = dq.popleft()
            curr_clearance = clearance[(x, y)]
            if curr_clearance > best_clearance:
                best_clearance = curr_clearance
                best_cell = (x, y)
            if curr_clearance >= max_possible:
                break
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = x + dx, y + dy
                neighbor = (nx, ny)
                if neighbor in safe_region and clearance[neighbor] == -1:
                    clearance[neighbor] = curr_clearance + 1
                    dq.append(neighbor)
        
        # print(f"Best cell (from mist): {best_cell}, Clearance: {best_clearance}")
        self.component_cache[component_id] = (safe_region, mist_boundary, wall_boundary, clearance, best_cell, best_clearance)
        return best_cell, best_clearance


    def get_candidate(self, x: int, y: int):
        """
        Given a starting coordinate (x, y), return a candidate safe cell (to 'escape' to)
        such that its clearance from mist (cells with value 8) is maximized.
        """
        if self.matrix[y][x] != 8:
            # If the starting cell is safe, use cached clearance
            return self.get_max_clearance_cell_with_clearance((x, y))[0]

        # Misted start: BFS to find safe components
        dq = deque([(x, y)])
        visited = {(x, y)}
        safe_components = {}  # Maps component_id to set of safe cells
        component_id = self.component_counter if hasattr(self, 'component_counter') else 0

        while dq:
            cx, cy = dq.popleft()
            if self.is_safe((cx, cy)):
                # Start a new safe component if not already in one
                if (cx, cy) not in self.cell_to_component:
                    comp = set()
                    comp_dq = deque([(cx, cy)])
                    comp.add((cx, cy))
                    self.cell_to_component[(cx, cy)] = component_id
                    while comp_dq:
                        sx, sy = comp_dq.popleft()
                        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                            nx, ny = sx + dx, sy + dy
                            neighbor = (nx, ny)
                            if (0 <= nx < self.width and 0 <= ny < self.height and
                                self.matrix[ny][nx] != 8 and self.matrix[ny][nx] != self.INF and
                                neighbor not in comp):
                                comp.add(neighbor)
                                comp_dq.append(neighbor)
                                self.cell_to_component[neighbor] = component_id
                                if neighbor in visited:
                                    visited.remove(neighbor)  # Ensure revisited as part of component
                    safe_components[component_id] = comp
                    component_id += 1
                    self.component_counter = component_id

            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                neighbor = (nx, ny)
                if neighbor not in visited:
                    visited.add(neighbor)
                    dq.append(neighbor)

        if not safe_components:
            return None

        # Find best candidate across components
        best_candidate = None
        best_clearance = -1
        for comp_id, comp in safe_components.items():
            # Use a representative cell from the component
            safe_cell = next(iter(comp))
            if comp_id in self.component_cache:
                _, _, _, _, candidate, clearance = self.component_cache[comp_id]
                #print(f"Cache hit for component {comp_id}, candidate: {candidate}, clearance: {clearance}")
            else:
                candidate, clearance = self.get_max_clearance_cell_with_clearance(safe_cell)
            if clearance > best_clearance:
                best_clearance = clearance
                best_candidate = candidate

        return best_candidate
