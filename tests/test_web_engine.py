import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node not installed")
class WebEngineTests(unittest.TestCase):
    def test_js_engine_rules(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "test_game_js.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_js_maze_matches_python_maze(self):
        from pacman.game import MAZE, PAC_START, GHOST_STARTS
        r = subprocess.run(["node", "-e", "const g=require('./web/game.js');console.log(JSON.stringify([g.MAZE,g.PAC_START,g.GHOST_STARTS]))"],
                           capture_output=True, text=True, cwd=ROOT)
        import json
        maze, pac, ghosts = json.loads(r.stdout)
        self.assertEqual(maze, MAZE)
        self.assertEqual(tuple(pac), PAC_START)
        self.assertEqual([tuple(g) for g in ghosts], GHOST_STARTS)


if __name__ == "__main__":
    unittest.main()
