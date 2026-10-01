import random
import unittest

from pacman.agents import bfs_agent, random_agent
from pacman.game import GHOST_STARTS, MAZE, PAC_START, Game
from pacman.run import play


class GameTests(unittest.TestCase):
    def test_maze_is_rectangular_and_starts_are_open(self):
        self.assertEqual({len(r) for r in MAZE}, {19})
        g = Game()
        for p in [PAC_START, *GHOST_STARTS]:
            self.assertNotEqual(MAZE[p[1]][p[0]], "#")

    def test_legal_actions_and_illegal_raises(self):
        g = Game()
        self.assertEqual(set(g.legal_actions()), {"left", "right"})  # matches Ollama replay: only left/right at start
        with self.assertRaises(ValueError):
            g.step("down")  # (9,16) is a wall

    def test_tunnel_wraps(self):
        g = Game()
        self.assertEqual(g.neighbor((0, 9), "left"), (18, 9))
        self.assertEqual(g.neighbor((18, 9), "right"), (0, 9))

    def test_eating_dot_scores(self):
        g = Game()
        g.pac = (8, 15)
        g.dots = {(7, 15), (1, 1)}
        g.ghosts = [(1, 19)] * 3
        g.step("left")
        self.assertEqual(g.score, 10)
        self.assertEqual(g.dots, {(1, 1)})

    def test_catch_costs_life_and_resets(self):
        g = Game()
        g.pac = (8, 15)
        g.ghosts = [(7, 15), (1, 19), (1, 19)]
        g.ghost_dir = [None] * 3
        # ghost adjacent: pacman moves into it -> same cell or swap -> caught
        g.step("left")
        self.assertTrue(g.caught)
        self.assertEqual(g.lives, 2)
        self.assertEqual(g.pac, PAC_START)
        self.assertEqual(g.ghosts, GHOST_STARTS)

    def test_ghosts_never_enter_walls(self):
        g = Game(seed=3, max_steps=300)
        rng = random.Random(0)
        while not g.over:
            g.step(random_agent(g, rng))
            for x, y in g.ghosts:
                self.assertNotEqual(MAZE[y][x], "#")

    def test_deterministic_with_seed(self):
        _, a = play(random_agent, seed=7)
        _, b = play(random_agent, seed=7)
        self.assertEqual(a, b)

    def test_game_over_conditions(self):
        g = Game(max_steps=1)
        g.step(g.legal_actions()[0])
        self.assertTrue(g.over)
        with self.assertRaises(RuntimeError):
            g.step("left")

    def test_bfs_beats_random(self):
        bfs = [play(bfs_agent, seed=s)[0].score for s in range(10)]
        rnd = [play(random_agent, seed=s)[0].score for s in range(10)]
        self.assertGreater(sum(bfs), sum(rnd))
        print(f"\nbfs mean={sum(bfs)/10:.0f} random mean={sum(rnd)/10:.0f}")


if __name__ == "__main__":
    unittest.main()
