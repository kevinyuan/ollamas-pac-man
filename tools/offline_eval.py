"""Offline prompt evaluation: how often does Nimble pick the move a safe BFS would, and how often
does it step next to a ghost?  One request per state, no game played.

  PYTHONPATH=. python3 tools/offline_eval.py --base-url http://localhost:11434 T D DM
"""
import argparse
import json
import random
import statistics
import time
import urllib.request

from pacman.agents import bfs_agent
from pacman.game import Game
from pacman.nimble import (FORMATS, board, build_request, describe_danger, distances, manhattan)
from pacman.nimble import DEFAULT_URL

HOW = ("Board: 19 columns x 21 rows, one char per cell, rows listed top to bottom. "
       "#=wall .=dot P=you G=ghost space=empty floor. up=previous row, down=next row, left/right=same row. "
       "Choose the move that reaches the nearest dot fastest and never steps next to a ghost (G).")
DEFS = {"up": "move to the cell in the row above P", "down": "move to the cell in the row below P",
        "left": "move to the cell left of P", "right": "move to the cell right of P"}


def matrix(g, instructions, defs=False):
    crit = {a: (DEFS[a] if defs else None) for a in g.legal_actions()}
    return {"model": "nimble", "state": board(g),
            "questions": {"move": {"type": "choice", "instructions": instructions, "criteria": crit}}}


VARIANTS = {
    "M0": lambda g: matrix(g, "Pac-Man board (P=you, G=ghost, .=dot, #=wall). Which move is best?"),
    "M1": lambda g: matrix(g, HOW),
    "M2": lambda g: matrix(g, HOW, defs=True),
    "T": build_request,
    "D": FORMATS["danger"],
    "DM": FORMATS["danger-min"],
    "L1": FORMATS["coords"],
    "L1W": FORMATS["coords-words"],
    "F1": FORMATS["rays"],
    "N1": FORMATS["neighbors"],
    "F2": FORMATS["rays-text"],
    "F3": FORMATS["rays-text-q"],
    "F4": FORMATS["rays-text-q2"],
    "D2": FORMATS["danger-text"],
    "F5": FORMATS["rays-side"],
    "F6": FORMATS["rays-side-dots"],
}


def rule_l3(g):
    """No-model control for D/T features: skip DEADLY, prefer safe over risky, then nearest dot."""
    import re
    d = describe_danger(g)

    def key(a):
        t = d[a]
        m = re.search(r"nearest dot (\d+)", t)
        return (0 if t.startswith("safe") else 1 if t.startswith("risky") else 2,
                0 if "eats a dot" in t else int(m.group(1)) if m else 99)
    return min(d, key=key)


def rule_l1(g):
    """No-model control for L1 info (coordinates only): Manhattan distances, nothing else."""
    from pacman.nimble import COORD_DOT_RADIUS

    def key(a):
        n = g.neighbor(g.pac, a)
        gh = min(manhattan(g, n, x) for x in g.ghosts)
        dots = [manhattan(g, n, p) for p in g.dots if manhattan(g, p, g.pac) <= COORD_DOT_RADIUS]
        return (gh <= 1, gh == 2, 0 if n in g.dots else min(dots, default=99))
    return min(g.legal_actions(), key=key)


def rule_f1(g):
    """No-model control for F1 flags: avoid near ghost, then prefer far-ghost-free, then a dot ahead."""
    from pacman.nimble import describe_rays

    def key(a):
        t = describe_rays(g)[a]
        return ("ghost near" in t, "ghost far" in t, "no dot" in t)
    return min(g.legal_actions(), key=key)


def rule_n1(g):
    """No-model control for N1: never a ghost cell, prefer a dot, else first legal."""
    from pacman.nimble import describe_neighbors
    d = describe_neighbors(g)
    return min(d, key=lambda a: (d[a] == "ghost", d[a] != "dot"))


def rule_f5(g):
    """No-model control for F5 facts: a near ghost or a side-passage ghost is worst, then a far ghost, then no dot."""
    from pacman.nimble import describe_rays_side

    def key(a):
        t = describe_rays_side(g)[a]
        return ("ghost near" in t or "side ghost" in t, "ghost far" in t, "no dot" in t)
    return min(g.legal_actions(), key=key)


def rule_side3(g):
    """F5 plus a second tier for a ghost 2-3 cells down a side passage (can come out behind or beside me)."""
    from pacman.nimble import describe_rays, side_ray

    def key(a):
        t = describe_rays(g)[a]
        sr = side_ray(g, a)
        return ("ghost near" in t or sr == 1, sr is not None, "ghost far" in t, "no dot" in t)
    return min(g.legal_actions(), key=key)


def rule_f6(g):
    """F6 controls: F5's safety tiers, then a dot ahead, then the direction toward the nearest dot (Manhattan)."""
    from pacman.nimble import describe_rays_side, toward_nearest_dot

    def key(a):
        t = describe_rays_side(g)[a]
        return ("ghost near" in t or "side ghost" in t, "ghost far" in t, "no dot" in t, not toward_nearest_dot(g, a))
    return min(g.legal_actions(), key=key)


RULES = {"RF6": rule_f6, "RFS3": rule_side3, "R3": rule_l3, "R1": rule_l1, "RF": rule_f1, "RN": rule_n1, "RF5": rule_f5}


def make_states(n, seed=0):
    """States from epsilon-noisy BFS games so that ghosts come close; half are 'danger' states."""
    rng = random.Random(seed)
    pool = []
    for gs in range(20, 30):
        g, r = Game(seed=gs, max_steps=300), random.Random(gs)
        while not g.over:
            if len(g.legal_actions()) >= 2 and rng.random() < 0.25:
                s = Game(seed=0)
                s.__dict__.update({k: (v.copy() if hasattr(v, "copy") else v) for k, v in g.__dict__.items()})
                s.ghosts = list(g.ghosts)
                pool.append(s)
            g.step(rng.choice(g.legal_actions()) if r.random() < 0.3 else bfs_agent(g, r))
    near = [s for s in pool if danger(s)]
    far = [s for s in pool if not danger(s)]
    rng.shuffle(near), rng.shuffle(far)
    return near[:n // 2] + far[:n - min(len(near), n // 2)], len(near[:n // 2])


def ghost_dist(g, a):
    n = g.neighbor(g.pac, a)
    return min(distances(g, gh).get(n, 99) for gh in g.ghosts)


def danger(g):  # some legal move lands within 2 steps of a ghost
    return any(ghost_dist(g, a) <= 2 for a in g.legal_actions())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_URL)
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("variants", nargs="*", default=["T", "D", "DM"])
    a = ap.parse_args()
    states, n_danger = make_states(a.n)
    print(f"{len(states)} states ({n_danger} danger states)")

    def ask(req):
        r = urllib.request.Request(a.base_url + "/v1/systemone", json.dumps(req).encode(),
                                   {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r, timeout=60))["answers"]["move"]

    for name in a.variants:
        agree = unsafe = d_agree = d_unsafe = 0
        top, t0 = [], time.time()
        for i, g in enumerate(states):
            if name in RULES:
                c, ans = RULES[name](g), {"probabilities": {"x": 1.0}}
            else:
                ans = ask(VARIANTS[name](g))
                c = ans["choice"] if ans["choice"] in g.legal_actions() else max(ans["probabilities"], key=ans["probabilities"].get)
            ok, bad = c == bfs_agent(g), ghost_dist(g, c) <= 1
            agree += ok
            unsafe += bad
            if i < n_danger:
                d_agree += ok
                d_unsafe += bad
            top.append(max(ans["probabilities"].values()))
        n = len(states)
        print(f"{name:3s} agree {agree/n:4.0%}  unsafe {unsafe/n:4.0%} | danger-states agree {d_agree/n_danger:4.0%} "
              f"unsafe {d_unsafe/n_danger:4.0%} | top-prob {statistics.mean(top):.2f} | {(time.time()-t0)/n*1000:.0f} ms", flush=True)
    print("reference: random agree %.0f%%, random unsafe %.0f%%, bfs unsafe %.0f%%" % (
        100 * statistics.mean(1 / len(g.legal_actions()) for g in states),
        100 * statistics.mean(sum(ghost_dist(g, x) <= 1 for x in g.legal_actions()) / len(g.legal_actions()) for g in states),
        100 * statistics.mean(ghost_dist(g, bfs_agent(g)) <= 1 for g in states)))


if __name__ == "__main__":
    main()
