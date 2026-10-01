"""How often does the model walk into a deadly option when a safe one was on offer?

  PYTHONPATH=. python3 tools/lure_metric.py web/nimble_f5_s1.json:1 ...   (path:seed, replayed deterministically)

An option is deadly when a ghost is within 1 step of the cell it leads to (what a catch needs); safe when >= 2.
'Opportunity' = a step offering both kinds. The rate is picks of a deadly option / opportunities.
Also split by whether the deadly option also showed a dot ahead (the lure).
"""
import json
import sys
from collections import defaultdict

from pacman.game import Game
from pacman.nimble import distances, ray


def analyse(path, seed):
    log = json.load(open(path))["moves"]
    g = Game(seed=seed)
    opp = ign = lured_opp = lured_ign = 0
    for m in log:
        a = m["r"]["choice"]
        legal = g.legal_actions()
        gm = [distances(g, gh) for gh in g.ghosts]
        gd = {x: min(d.get(g.neighbor(g.pac, x), 99) for d in gm) for x in legal}
        deadly = [x for x in legal if gd[x] <= 1]
        if deadly and any(gd[x] >= 2 for x in legal):
            opp += 1
            ign += gd[a] <= 1
            if any(ray(g, x)[0] for x in deadly):
                lured_opp += 1
                lured_ign += gd[a] <= 1
        g.step(a)
    return len(log), opp, ign, lured_opp, lured_ign


if __name__ == "__main__":
    groups = defaultdict(lambda: [0, 0, 0, 0, 0])
    for arg in sys.argv[1:]:
        p, s = arg.rsplit(":", 1)
        name = p.split("/")[-1].rsplit("_s", 1)[0]
        for i, v in enumerate(analyse(p, int(s))):
            groups[name][i] += v
    print(f"{'run':22s} {'steps':>6s} {'opportunities':>13s} {'walked in':>9s} {'rate':>6s} | {'with dot lure':>13s} {'walked in':>9s} {'rate':>6s}")
    for name, (steps, opp, ign, lo, li) in groups.items():
        print(f"{name:22s} {steps:6d} {opp:13d} {ign:9d} {ign / max(opp, 1):6.0%} | {lo:13d} {li:9d} {li / max(lo, 1):6.0%}")
