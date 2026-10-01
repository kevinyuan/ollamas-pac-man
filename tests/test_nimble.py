import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from pacman.game import Game
from pacman.nimble import NimbleAgent, build_request, describe_actions, local_view
from pacman.run import play


class Handler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.requests.append((self.path, body))
        crit = list(body["questions"]["move"]["criteria"])
        # mock model: prefer the move whose text mentions "eats a dot", else the first option
        pick = next((k for k, v in body["questions"]["move"]["criteria"].items() if "eats a dot" in v), crit[0])
        probs = {k: (0.7 if k == pick else 0.3 / max(1, len(crit) - 1)) for k in crit}
        out = {"model": body["model"], "answers": {"move": {
            "type": "choice", "choice": pick, "probabilities": probs, "confidence": 0.5}}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class NimbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_request_shape(self):
        g = Game()
        req = build_request(g)
        self.assertEqual(set(req["state"]), {"rules", "view", "dots_left", "lives"})
        self.assertEqual(set(req["questions"]["move"]["criteria"]), set(g.legal_actions()))
        self.assertEqual(req["questions"]["move"]["type"], "choice")

    def test_local_view_marks_pacman_and_is_square(self):
        rows = local_view(Game()).split("\n")
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(len(r) == 7 for r in rows))
        self.assertEqual(rows[3][3], "P")

    def test_describe_actions_mentions_dots(self):
        d = describe_actions(Game())
        self.assertTrue(all("nearest dot" in v for v in d.values()))

    def test_full_game_against_mock_server(self):
        agent = NimbleAgent(self.url)
        game, log = play(agent, seed=1, max_steps=40)
        self.assertEqual(len(log), game.steps)
        self.assertIn("probabilities", log[0]["r"])
        self.assertTrue(all(p == "/v1/systemone" for p, _ in Handler.requests))
        self.assertEqual(len(agent.latencies), game.steps)

    def test_illegal_choice_falls_back_to_legal(self):
        agent = NimbleAgent(self.url)
        agent.query = lambda payload: {"answers": {"move": {
            "choice": "down", "probabilities": {"down": 0.9, "left": 0.1}}}}
        g = Game()  # 'down' is a wall at start
        self.assertEqual(agent(g), "left")


if __name__ == "__main__":
    unittest.main()


class DangerTests(unittest.TestCase):
    def test_adjacent_ghost_is_deadly_and_far_is_safe(self):
        from pacman.nimble import describe_danger
        g = Game()
        g.ghosts = [(7, 15), (1, 19), (1, 19)]  # pacman at (9,15): left target (8,15) is next to the ghost
        d = describe_danger(g)
        self.assertTrue(d["left"].startswith("DEADLY"))
        self.assertTrue(d["right"].startswith("safe"))
        g.ghosts = [(1, 19)] * 3
        self.assertTrue(all(v.startswith("safe") for v in describe_danger(g).values()))


class SideGhostTests(unittest.TestCase):
    def test_side_ghost_detected_beside_target_cell(self):
        from pacman.nimble import describe_rays_side_text, side_ghost
        g = Game()
        g.pac = (3, 13)                       # moving right to (4,13); the cell below, (4,14), is open
        g.ghosts = [(4, 14), (1, 19), (1, 19)]
        self.assertTrue(side_ghost(g, "right"))
        self.assertIn("side passage right next", describe_rays_side_text(g)["right"])
        g.ghosts = [(1, 19), (1, 19), (1, 19)]
        self.assertFalse(side_ghost(g, "right"))
        self.assertIn("side passages are clear", describe_rays_side_text(g)["right"])


class NearestDotTests(unittest.TestCase):
    def test_toward_nearest_dot(self):
        from pacman.nimble import describe_rays_side_dots_text, toward_nearest_dot
        g = Game()
        g.pac, g.ghosts = (9, 15), [(1, 19)] * 3
        g.dots = {(5, 15), (15, 15)}         # nearest is 4 to the left
        self.assertTrue(toward_nearest_dot(g, "left"))
        self.assertFalse(toward_nearest_dot(g, "right"))
        d = describe_rays_side_dots_text(g)
        self.assertTrue(d["left"].endswith("the nearest dot is toward that way."))
        self.assertTrue(d["right"].endswith("the nearest dot is not toward that way."))


class GradeTests(unittest.TestCase):
    def test_deadly_option_has_no_dot_lure(self):
        from pacman.nimble import describe_rays_grade_text
        g = Game()
        g.pac, g.ghosts = (3, 13), [(4, 14), (1, 19), (1, 19)]   # moving right lands next to the ghost below (4,13)
        d = describe_rays_grade_text(g)
        self.assertEqual(d["right"], "Moving right: a ghost is right there and will catch you.")
        self.assertNotIn("dot", d["right"])
        self.assertIn("side passages are clear", d["left"])
