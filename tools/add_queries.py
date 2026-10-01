"""Add the request ("q") of every move to old logs by replaying the game (same seed, same moves).

  PYTHONPATH=. python3 tools/add_queries.py web/nimble_f5_s1.json:1:rays-side [...]

Each argument is path:seed:fmt (fmt as in `python -m pacman.run --fmt`). The replay is checked against the
log (same catches, recorded choice is a legal move, criteria keys are exactly the legal moves).
"""
import json
import sys

from pacman.game import Game
from pacman.nimble import FORMATS


def add(path, seed, fmt):
    log = json.load(open(path))
    g, build = Game(seed=seed), FORMATS[fmt]
    for t, m in enumerate(log["moves"]):
        req = build(g)
        crit = req["questions"]["move"]["criteria"]
        assert set(crit) == set(g.legal_actions()), f"{path} step {t}: criteria != legal actions"
        assert m["r"]["choice"] in crit, f"{path} step {t}: logged choice not offered"
        m["q"] = {k: v for k, v in req.items() if k != "model"}
        caught = g.step(m["r"]["choice"])
        assert caught == bool(m.get("c")), f"{path}: replay diverged at step {t}"
    log["fmt"] = fmt
    json.dump(log, open(path, "w"))
    print(f"{path}: {len(log['moves'])} moves, fmt={fmt}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p, s, f = arg.split(":")
        add(p, int(s), f)
