"""Why did a logged game lose? Re-simulate it (same seed, same moves) and, at every step, compare the
chosen move with the alternatives by ghost distance to the target cell.

  PYTHONPATH=. python3 tools/failure_analysis.py web/game_nimble.json:1 web/nimble_matrix_s1.json:1
"""
import json
import sys

from pacman.game import Game
from pacman.nimble import distances


def analyse(path, seed):
    log = json.load(open(path))["moves"]
    g = Game(seed=seed)
    rows, catches = [], []
    for t, m in enumerate(log):
        a = m["r"]["choice"]
        legal = g.legal_actions()
        gm = [distances(g, gh) for gh in g.ghosts]
        gd = {x: min(d.get(g.neighbor(g.pac, x), 99) for d in gm) for x in legal}
        rows.append((t, a, gd))
        caught = g.step(a)
        assert caught == bool(m.get("c")), f"replay diverged at step {t}"
        if caught:
            catches.append(t)
    return rows, catches


def report(path, seed):
    rows, catches = analyse(path, seed)
    n = len(rows)
    deadly_pick = forced = wrong = 0
    for t, a, gd in rows:
        has_safe = any(v >= 2 for v in gd.values())
        if gd[a] <= 1:
            deadly_pick += 1
            wrong += has_safe
        forced += not has_safe
    print(f"\n{path} (seed {seed}): {n} steps, {len(catches)} catches at steps {catches}")
    print(f"  steps with NO safe move (all targets within 1 of a ghost): {forced}/{n}")
    print(f"  steps that picked a deadly move: {deadly_pick}; of those a safe move existed (decision error): {wrong}")
    for c in catches:
        t, a, gd = rows[c]
        verdict = "DECISION ERROR (a safe move existed)" if any(v >= 2 for v in gd.values()) else "forced (no safe move)"
        back = []
        for k in range(max(0, c - 4), c + 1):
            _, ak, gk = rows[k]
            back.append(f"{ak}:{gk[ak]}/{max(gk.values())}")
        print(f"  catch@{c}: chose {a} (ghost dist {gd[a]}), options {gd} -> {verdict}")
        print(f"      last 5 picks as choice:ghost-dist/best-available  {'  '.join(back)}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p, s = arg.rsplit(":", 1)
        report(p, int(s))
