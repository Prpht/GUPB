import pickle
import sys
from collections import defaultdict
from itertools import product
from math import inf

from tqdm import tqdm

from gupb.controller.krowa123.utils import neighboring_coords
from gupb.model.arenas import Arena


def floyd_warshall(arena: Arena):
    passable = {c for c, t in arena.terrain.items() if t.terrain_passable()}

    dist = {c: {c: inf for c in passable} for c in passable}
    nxt = defaultdict(defaultdict)
    for c in passable:
        dist[c][c] = 0
    for c in passable:
        for cc in neighboring_coords(c):
            if cc in passable:
                dist[c][cc] = 1
                nxt[c][cc] = cc
    for k in tqdm(passable, desc=f"Computing all-pairs shortest paths for '{arena.name}' arena"):
        for i, j in product(passable, repeat=2):
            sum_ik_kj = dist[i][k] + dist[k][j]
            if dist[i][j] > sum_ik_kj:
                dist[i][j] = sum_ik_kj
                nxt[i][j] = nxt[i][k]
    return dist, nxt


if __name__ == '__main__':
    arena = sys.argv[1]
    file = f"gupb/controller/krowa123/pathfinding/data/{arena}.p"
    # fw = floyd_warshall(Arena.load(arena))
    # pickle.dump(fw, open(file, "wb"))
    print(pickle.load(open(file, "rb")))
