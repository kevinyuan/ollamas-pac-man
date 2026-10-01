"""Controlled micro-tasks: can Nimble do spatial arithmetic, and which encoding unlocks it?

  PYTHONPATH=. python3 tools/probe_capability.py --base-url http://localhost:11434 -n 50

Task A: which move gets closest to the dot?     Task B: which move gets farthest from the ghost?
Offsets have both dx and dy non-zero, so exactly 2 of the 4 moves are correct (chance = 50%).
"""
import argparse
import json
import random
import time
import urllib.request
from pacman.nimble import DEFAULT_URL

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def make_case(rng):
    px, py = rng.randint(6, 12), rng.randint(6, 14)
    dx, dy = rng.choice([-1, 1]) * rng.randint(1, 5), rng.choice([-1, 1]) * rng.randint(1, 5)
    return (px, py), (dx, dy)


def correct(off, task):
    d0 = abs(off[0]) + abs(off[1])
    best = {}
    for a, (mx, my) in DIRS.items():
        best[a] = abs(off[0] - mx) + abs(off[1] - my) - d0   # change in distance after moving
    target = min(best.values()) if task == "A" else max(best.values())
    return {a for a, v in best.items() if v == target}


def words(off, name):
    h = f"{abs(off[0])} {'right' if off[0] > 0 else 'left'}"
    v = f"{abs(off[1])} {'down' if off[1] > 0 else 'up'}"
    return f"The {name} is {h} and {v} of you."


def encode(enc, pac, off, name):
    tgt = (pac[0] + off[0], pac[1] + off[1])
    if enc == "abs":
        return {"pacman": list(pac), name: list(tgt)}
    if enc == "rel":
        return {f"{name}_offset": list(off)}
    if enc == "words":
        return {"situation": words(off, name)}
    if enc == "flags":
        return {f"{name}_is": f"{'right' if off[0] > 0 else 'left'} and {'down' if off[1] > 0 else 'up'}"}


COORD_NOTE = "x grows to the right, y grows downward. Offsets are target minus you. "
ASK = {"A": "Which move gets you closest to the dot?", "B": "Which move gets you farthest from the ghost?"}
NAME = {"A": "dot", "B": "ghost"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_URL)
    ap.add_argument("-n", type=int, default=50)
    a = ap.parse_args()
    rng = random.Random(0)
    cases = [make_case(rng) for _ in range(a.n)]

    def ask(req):
        r = urllib.request.Request(a.base_url + "/v1/systemone", json.dumps(req).encode(), {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r, timeout=60))["answers"]["move"]

    print(f"n={a.n} per cell, chance=50%  (95% CI about +-14pt)")
    for task in "AB":
        for enc in ("abs", "rel", "words", "flags"):
            ok, t0, tops = 0, time.time(), []
            for pac, off in cases:
                req = {"model": "nimble", "state": encode(enc, pac, off, NAME[task]),
                       "questions": {"move": {"type": "choice", "instructions": COORD_NOTE + ASK[task],
                                              "criteria": {d: None for d in DIRS}}}}
                ans = ask(req)
                ok += ans["choice"] in correct(off, task)
                tops.append(max(ans["probabilities"].values()))
            print(f"task {task} {enc:6s} correct {ok/a.n:4.0%}  top-prob {sum(tops)/a.n:.2f}  {(time.time()-t0)/a.n*1000:.0f} ms", flush=True)


if __name__ == "__main__":
    main()
