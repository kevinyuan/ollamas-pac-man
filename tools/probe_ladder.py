"""Add complexity one step at a time (relative-direction words, open board) to find where Nimble breaks.

  PYTHONPATH=. python3 tools/probe_ladder.py --base-url http://localhost:11434 -n 50

a   1 dot + 1 ghost; correct = safest-and-closest (a move is safe if it ends >=2 from every ghost)
b   1 dot + 3 ghosts (one near, two far)
c1  6 dots in random order, 1 far ghost; correct = approach the nearest dot
c2  same, listed nearest-first
Cases with no safe move are skipped. 'conflict' = some dot-approaching move is unsafe.
"""
import argparse
import json
import random
import time
import urllib.request
from pacman.nimble import DEFAULT_URL

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
man = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
step = lambda p, d: (p[0] + DIRS[d][0], p[1] + DIRS[d][1])


def phrase(o):
    parts = ([f"{o[0]} right"] if o[0] > 0 else [f"{-o[0]} left"] if o[0] < 0 else []) + \
            ([f"{o[1]} down"] if o[1] > 0 else [f"{-o[1]} up"] if o[1] < 0 else [])
    return " ".join(parts) or "here"


def rnd_off(rng, lo, hi, both=False):
    while True:
        o = (rng.randint(-hi, hi), rng.randint(-hi, hi))
        if lo <= man(o, (0, 0)) <= hi and (not both or (o[0] and o[1])):
            return o


def case(level, rng):
    me = (0, 0)
    if level in ("a", "b"):
        dot = rnd_off(rng, 3, 7, both=True)
        ghosts = [rnd_off(rng, 2, 3)] + ([rnd_off(rng, 5, 8), rnd_off(rng, 5, 8)] if level == "b" else [])
        rng.shuffle(ghosts)
        safe = [d for d in DIRS if all(man(step(me, d), g) >= 2 for g in ghosts)]
        if not safe:
            return None
        best = min(man(step(me, d), dot) for d in safe)
        ok = {d for d in safe if man(step(me, d), dot) == best}
        toward = {d for d in DIRS if man(step(me, d), dot) < man(me, dot)}
        state = {"ghosts": "; ".join(phrase(g) for g in ghosts), "dots": phrase(dot)}
        return state, ok, bool(toward - set(safe))
    ghost = rnd_off(rng, 7, 9)
    dots = [rnd_off(rng, 1, 5) for _ in range(6)]
    dist = sorted(man(d, me) for d in dots)
    if len(set(dots)) < 6 or dist[0] == dist[1]:
        return None
    near = min(dots, key=lambda d: man(d, me))
    ok = {d for d in DIRS if man(step(me, d), near) < man(me, near)}
    if level == "c2":
        dots.sort(key=lambda d: man(d, me))
    return {"ghosts": phrase(ghost), "dots": "; ".join(phrase(d) for d in dots)}, ok, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_URL)
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("levels", nargs="*", default=["a", "b", "c1", "c2"])
    a = ap.parse_args()

    def ask(req):
        r = urllib.request.Request(a.base_url + "/v1/systemone", json.dumps(req).encode(), {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r, timeout=60))["answers"]["move"]

    for level in a.levels:
        rng, cases = random.Random(1), []
        while len(cases) < a.n:
            c = case(level, rng)
            if c:
                cases.append(c)
        ok = conf_ok = n_conf = 0
        t0, chance = time.time(), sum(len(c[1]) / 4 for c in cases) / a.n
        for state, good, conflict in cases:
            ans = ask({"model": "nimble", "state": state, "questions": {"move": {
                "type": "choice", "criteria": {d: None for d in DIRS},
                "instructions": "Ghost and dot positions are given relative to you"
                                + (", nearest first. " if level == "c2" else ". ")
                                + "Which move is best? Eat dots, never move next to a ghost."}}})
            hit = ans["choice"] in good
            ok += hit
            n_conf += conflict
            conf_ok += hit and conflict
        print(f"level {level:2s} correct {ok/a.n:4.0%} (chance {chance:3.0%})  conflict cases {n_conf}: "
              f"{(conf_ok/n_conf if n_conf else float('nan')):4.0%}  {(time.time()-t0)/a.n*1000:.0f} ms", flush=True)


if __name__ == "__main__":
    main()
