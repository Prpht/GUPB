import numpy as np
import os


def import_map(arena_name):
    """
    Import map and calculate basic properties.
    """
    arena_filepath = os.path.join('resources', 'arenas', f'{arena_name}.gupb')

    txt = []

    with open(arena_filepath, mode='r') as file:
        for line in file:
            txt += [line.strip("\n")]

    island_ar = np.array([list(i) for i in txt])

    height = island_ar.shape[0]
    width = island_ar.shape[1]

    traversable = np.logical_and(island_ar != '=', island_ar != '#').astype(np.int32)
    is_wall = (island_ar == '#').astype(np.int32)

    start = ((height - 1) // 2, (width - 1) // 2)
    best_pos = None
    best_dist = 9999

    for _ in range(150):
        pos = (start[0] + np.random.randint(-8, 9), start[1] + np.random.randint(-8, 9))
        if island_ar[pos] == '.':
            dist = (start[0] - pos[0]) ** 2 + (start[1] - pos[1]) ** 2
            if dist < best_dist:
                best_pos = pos
                best_dist = dist

    start = best_pos

    # Create initial weapons knowledge dict
    weapons_knowledge = {}
    for i in range(height):
        for j in range(width):
            if island_ar[i, j] == 'A':
                weapons_knowledge[(i, j)] = 'A'
            elif island_ar[i, j] == 'B':
                weapons_knowledge[(i, j)] = 'B'
            elif island_ar[i, j] == 'S':
                weapons_knowledge[(i, j)] = 'S'
            elif island_ar[i, j] == 'M':
                weapons_knowledge[(i, j)] = 'M'

    return height, width, traversable, is_wall, start, weapons_knowledge


def map_clustering(height, width, start, traversable):
    """
    Make map clustering to allow easier path-finding.
    """
    # Initial cluster calculation by BFS in BFS
    clusters = np.zeros([height, width], dtype=np.int32)
    current_cluster = 1
    stack = [start]
    directions = np.array([[-1, 0], [1, 0], [0, -1], [0, 1]])

    while stack:
        pos = stack.pop(0)

        if clusters[pos] == 0:
            clusters[pos] = current_cluster

            substack = [pos]
            i = 0
            while i < 6 and substack:
                i += 1
                pos = substack.pop(0)

                for dxdy in directions:
                    new_pos = tuple(pos + dxdy)
                    if traversable[new_pos] and clusters[new_pos] == 0:
                        clusters[new_pos] = current_cluster
                        substack.append(new_pos)

            for pos in substack:
                clusters[pos] = 0

            stack.extend(substack)
            current_cluster += 1

    # Get derivable cluster information in valid cells
    c = clusters.reshape(-1)
    xs = np.tile(np.arange(width), [width, 1]).reshape(-1)
    ys = np.tile(np.arange(height).reshape(-1, 1), [1, height]).reshape(-1)

    xs = xs[c > 0]
    ys = ys[c > 0]
    c = c[c > 0]

    counts = np.zeros(np.max(c), dtype=np.int32)
    np.add.at(counts, c - 1, 1)

    proto_x = np.zeros(np.max(c), dtype=np.int32)
    proto_y = np.zeros(np.max(c), dtype=np.int32)
    np.put(proto_x, c - 1, xs)
    np.put(proto_y, c - 1, ys)

    # Merge tiny clusters into neighbors
    for i in np.arange(counts.shape[0])[counts < 5]:
        stack = [(proto_y[i], proto_x[i])]

        j = 0
        c_found = 0

        while j < len(stack):
            pos = stack[j]

            for dxdy in directions:
                new_pos = tuple(pos + dxdy)

                if clusters[new_pos] == i + 1:
                    if new_pos not in stack:
                        stack.append(new_pos)
                else:
                    if c_found == 0:
                        c_found = clusters[new_pos]

            j += 1

        counts[i] = 0
        for pos in stack:
            clusters[pos] = c_found

    clusters = np.r_[0, np.cumsum(counts > 0) * (counts > 0)][clusters]

    # Get derivable cluster information in valid cells again (final)
    c = clusters.reshape(-1)
    xs = np.tile(np.arange(width), [width, 1]).reshape(-1)
    ys = np.tile(np.arange(height).reshape(-1, 1), [1, height]).reshape(-1)

    xs = xs[c > 0]
    ys = ys[c > 0]
    c = c[c > 0]

    counts = np.zeros(np.max(c), dtype=np.int32)
    np.add.at(counts, c - 1, 1)

    proto_x = np.zeros(np.max(c), dtype=np.int32)
    proto_y = np.zeros(np.max(c), dtype=np.int32)
    np.put(proto_x, c - 1, xs)
    np.put(proto_y, c - 1, ys)

    # Get neighbors pairs and construct adjacency dictionary
    neighbors = np.concatenate([
        np.stack([clusters[:, 1:], clusters[:, :-1]], axis=-1).reshape(-1, 2),
        np.stack([clusters[1:, :], clusters[:-1, :]], axis=-1).reshape(-1, 2)
    ], axis=0)

    neighbors = neighbors[neighbors[:, 0] != neighbors[:, 1]]
    neighbors = neighbors[np.logical_and(neighbors[:, 0] != 0, neighbors[:, 1] != 0)]
    neighbors = list(
        set(map(lambda x: tuple(x), np.vstack([neighbors, neighbors[:, ::-1]]).tolist())))

    adj = {i: [] for i in range(1, counts.shape[0] + 1)}
    for c_from, c_to in neighbors:
        adj[c_from].append(c_to)

    return clusters, adj


def get_attackability_factors(height, width, traversable, is_wall):
    """
    This function calculates attackability factor on each square, which is a number squares and orientations
    from which one can be attacked by each available weapon.
    """
    attackability_bow = np.zeros([height, width])
    attackability_knife = np.zeros([height, width])
    attackability_axe = np.zeros([height, width])
    attackability_sword = np.zeros([height, width])
    attackability_amulet = np.zeros([height, width])

    # Bow
    stacks = []

    for i in range(height):
        counter = 0
        stack = []

        for j in range(width):
            if traversable[i, j]:
                counter += 1
                stack += [(i, j)]

            if is_wall[i, j]:
                counter = 0
                if stack: stacks += [stack]
                stack = []

        if stack: stacks += [stack]

    for stack in stacks:
        p = 2 * (len(stack) - 1)
        if p > 0:
            for pos in stack:
                attackability_bow[pos] += p

    stacks = []

    for j in range(width):
        counter = 0
        stack = []

        for i in range(height):
            if traversable[i, j]:
                counter += 1
                stack += [(i, j)]

            if is_wall[i, j]:
                counter = 0
                if stack: stacks += [stack]
                stack = []

        if stack: stacks += [stack]

    for stack in stacks:
        p = 2 * (len(stack) - 1)
        if p > 0:
            for pos in stack:
                attackability_bow[pos] += p

    # Knife and axe
    knife = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    axe = np.array([[2, 1, 2], [1, 0, 1], [2, 1, 2]])

    for i in range(1, height - 1):
        for j in range(1, width - 1):
            if traversable[i, j]:
                attackability_knife[i - 1:i + 2, j - 1:j + 2] += knife
                attackability_axe[i - 1:i + 2, j - 1:j + 2] += axe

    attackability_knife *= traversable
    attackability_axe *= traversable

    # Sword and amulet
    sword = [
        [(0, 1), (0, 2), (0, 3)],
        [(0, -1), (0, -2), (0, -3)],
        [(1, 0), (2, 0), (3, 0)],
        [(-1, 0), (-2, 0), (-3, 0)],
    ]
    amulet = [
        [(1, 1), (2, 2)],
        [(-1, 1), (-2, 2)],
        [(1, -1), (2, -2)],
        [(-1, -1), (-2, -2)],
    ]

    for i in range(1, height - 1):
        for j in range(1, width - 1):
            if traversable[i, j]:
                for area in sword:
                    for di, dj in area:
                        if i + di < 0 or j + dj < 0 or i + di >= height or j + dj >= width or is_wall[i + di, j + dj]:
                            break
                        attackability_sword[i + di, j + dj] += 1

                for area in amulet:
                    for di, dj in area:
                        if i + di < 0 or j + dj < 0 or i + di >= height or j + dj >= width or is_wall[i + di, j + dj]:
                            break
                        attackability_amulet[i + di, j + dj] += 4

    attackability_sword *= traversable
    attackability_amulet *= traversable

    return (
        attackability_bow,
        attackability_knife,
        attackability_axe,
        attackability_sword,
        attackability_amulet,
    )


def betweenness_centrality(adj, clusters):
    """
    Brandes' node betweenness centrality.
    http://snap.stanford.edu/class/cs224w-readings/brandes01centrality.pdf
    """
    C_B = {w: 0 for w in adj}

    for s in adj:
        S = []
        P = {w: [] for w in adj}
        sigma = {t: 0 for t in adj}
        sigma[s] = 1
        d = {t: -1 for t in adj}
        d[s] = 0
        Q = [s]

        while Q:
            v = Q.pop(0)
            S.append(v)

            for w in adj[v]:
                if d[w] < 0:
                    Q.append(w)
                    d[w] = d[v] + 1
                if d[w] == d[v] + 1:
                    sigma[w] = sigma[w] + sigma[v]
                    P[w].append(v)

        delta = {v: 0 for v in adj}

        while S:
            w = S.pop(-1)
            for v in P[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                C_B[w] += delta[w]

    C_B_max = max(C_B.values())
    C_B = {i: C_B[i] / C_B_max for i in C_B}

    betweenness = np.zeros_like(clusters)
    for i in adj:
        betweenness = np.where(clusters == i, C_B[i], betweenness)

    return betweenness


def non_clustering_coefficient(adj, clusters):
    """
    Planar Non-clustering coefficient
    """
    triangles = {s: 0 for s in adj}
    node_degree = {s: len(adj[s]) for s in adj}

    for s in adj:
        for u in adj[s]:
            for v in adj[u]:
                for w in adj[v]:
                    if w == s: triangles[s] += 1

    triangles = {s: triangles[s] / 2 for s in triangles}
    NC_C = {s: max(0, 1 - triangles[s] / node_degree[s]) for s in triangles}

    non_clustering = np.zeros_like(clusters)
    for i in adj:
        non_clustering = np.where(clusters == i, NC_C[i], non_clustering)

    return non_clustering


def borderedness_factor(adj, traversable, clusters):
    """
    Borderedness.
    """
    borderedness = traversable[1:-1, 1:-1] * (
            4 - traversable[1:-1, 2:] - traversable[1:-1, :-2]
            - traversable[2:, 1:-1] - traversable[:-2, 1:-1])

    c_border = clusters[1:-1, 1:-1].reshape(-1)
    borderedness = borderedness.reshape(-1)[c_border > 0]
    c_border = c_border[c_border > 0]

    border_count = np.zeros(np.max(c_border), dtype=np.int32)
    np.add.at(border_count, c_border - 1, borderedness)

    c = clusters.reshape(-1)
    c = c[c > 0]
    counts = np.zeros(np.max(c), dtype=np.int32)
    np.add.at(counts, c - 1, 1)

    borderedness = {i + 1: val for i, val in enumerate(np.minimum(border_count / counts, 2) / 2.0)}

    borderedness_fact = np.zeros_like(clusters)
    for i in adj:
        borderedness_fact = np.where(clusters == i, borderedness[i], borderedness_fact)

    return borderedness_fact


def analyze_map(arena_name):
    """
    Get the static analytics of the map.
    """
    (
        height,
        width,
        traversable,
        is_wall,
        start,
        weapons_knowledge,

    ) = import_map(arena_name)

    clusters, adj = map_clustering(height, width, start, traversable)

    (
        attackability_bow,
        attackability_knife,
        attackability_axe,
        attackability_sword,
        attackability_amulet,

    ) = get_attackability_factors(height, width, traversable, is_wall)

    betweenness = betweenness_centrality(adj, clusters)

    non_clustering = non_clustering_coefficient(adj, clusters)

    borderedness = borderedness_factor(adj, traversable, clusters)

    return {
        'height': height,
        'width': width,
        'traversable': traversable,
        'is_wall': is_wall,
        'start': start,
        'weapons_knowledge': weapons_knowledge,
        'clusters': clusters,
        'adj': adj,
        'attackability_bow': attackability_bow,
        'attackability_knife': attackability_knife,
        'attackability_axe': attackability_axe,
        'attackability_sword': attackability_sword,
        'attackability_amulet': attackability_amulet,
        'betweenness': betweenness,
        'non_clustering': non_clustering,
        'borderedness': borderedness,
    }
