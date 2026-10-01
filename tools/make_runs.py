"""Write web/runs.json: the list of recorded runs the Replay tab offers.  python3 tools/make_runs.py

Each web/*.json log is replayed (same seed, same moves) to get its final score, so the numbers shown on the page
are the engine's own. Seeds come from the file name (..._s3.json); game.json and game_nimble.json are seed 1.
"""
import json
import re
from pathlib import Path

from pacman.game import Game

WEB = Path(__file__).resolve().parent.parent / "web"
# fmt -> (group label shown in the picker, short description)
GROUPS = {
    "rays-grade": ("F7 · plain “will catch you”", 7),
    "rays-side-dots": ("F6 · plus nearest-dot hint", 6),
    "rays-side": ("F5 · plus side passages", 5),
    "rays-text-q2": ("F4 · straight-line sentences", 4),
    "rays": ("F1 · straight-line word fragments", 3),
    "danger": ("D · BFS labels (leaks the answer)", 2),
    "text": ("First try · 7×7 view + distances", 1),
    "matrix": ("Raw character matrix", 0),
    "bfs": ("Reference · breadth-first search, no model", -1),
}


def main():
    runs = []
    for path in sorted(WEB.glob("*.json")):
        if path.name == "runs.json":
            continue
        d = json.load(open(path))
        if "moves" not in d or "maze" not in d:
            continue
        m = re.search(r"_s(\d+)\.json$", path.name)
        seed = int(m.group(1)) if m else 1
        fmt = d.get("fmt") or ("text" if path.name == "game_nimble.json" else "bfs")
        g = Game(seed=seed)
        for mv in d["moves"]:
            g.step(mv["r"]["choice"])
        ms = [mv["ms"] for mv in d["moves"] if "ms" in mv]
        runs.append({"file": path.name, "fmt": fmt, "group": GROUPS[fmt][0], "order": GROUPS[fmt][1], "seed": seed,
                     "score": g.score, "steps": g.steps, "dotsLeft": len(g.dots) - (1 if (9, 15) in g.dots else 0),
                     "won": g.won, "avgMs": round(sum(ms) / len(ms)) if ms else None, "model": d.get("model")})
    runs.sort(key=lambda r: (-r["order"], r["seed"]))
    json.dump(runs, open(WEB / "runs.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(runs)} runs -> web/runs.json")
    for r in runs:
        print(f"  {r['group'][:38]:38s} seed {r['seed']}  {r['score']:5d} pts  {r['steps']:3d} moves  dots left {r['dotsLeft']:3d}")


if __name__ == "__main__":
    main()
