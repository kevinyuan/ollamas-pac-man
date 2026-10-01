import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pacman.agents import bfs_agent
from pacman.game import Game
from pacman.nimble import FORMATS

ROOT = Path(__file__).resolve().parent.parent
WEB_FORMATS = ["rays-text-q2", "rays-side", "rays-grade", "rays-side-dots"]


def sample_states(n_games=12, every=5):
    out = []
    for seed in range(n_games):
        g, rng = Game(seed=seed, max_steps=300), random.Random(seed)
        t = 0
        while not g.over:
            if t % every == 0:
                out.append((list(g.pac), [list(x) for x in g.ghosts], sorted([list(p) for p in g.dots]),
                            {f: FORMATS[f](g) for f in WEB_FORMATS}))
            g.step(rng.choice(g.legal_actions()) if rng.random() < 0.4 else bfs_agent(g, rng))
            t += 1
    return out


@unittest.skipUnless(shutil.which("node"), "node not installed")
class PromptParityTests(unittest.TestCase):
    def test_js_builders_match_python(self):
        cases = [{"pac": p, "ghosts": gh, "dots": d, "expected": e} for p, gh, d, e in sample_states()]
        self.assertGreater(len(cases), 100)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cases, f)
        r = subprocess.run(["node", str(ROOT / "tests" / "parity_prompts.js"), f.name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        print("\n" + r.stdout.strip())


if __name__ == "__main__":
    unittest.main()
