"""Pac-Man agent backed by Nimble (Ollama /v1/systemone decision API). Stdlib only."""
import json
import os
import time
import urllib.request
from collections import deque

from .game import DIRS

DEFAULT_URL = os.environ.get("TYPESAFE_BASE_URL", "http://localhost:11434")
VIEW_R = 3  # local view radius -> (2R+1)^2 cells

# Static text first so Ollama can reuse its prompt cache across steps.
RULES = ("Pac-Man. P=you, G=ghost, .=dot, #=wall, space=empty. You move one cell per turn. "
         "Eat all dots, avoid ghosts. A ghost within 2 steps is deadly.")


def distances(game, start, blocked=frozenset()):
    """BFS step distance from start to every reachable cell."""
    dist = {start: 0}
    queue = deque([start])
    while queue:
        pos = queue.popleft()
        for a in DIRS:
            n = game.neighbor(pos, a)
            if n and n not in dist and n not in blocked:
                dist[n] = dist[pos] + 1
                queue.append(n)
    return dist


def local_view(game, r=VIEW_R):
    px, py = game.pac
    rows = []
    for y in range(py - r, py + r + 1):
        line = []
        for x in range(px - r, px + r + 1):
            x %= game.w
            if not 0 <= y < game.h:
                line.append("#")
            elif (x, y) == game.pac:
                line.append("P")
            elif (x, y) in game.ghosts:
                line.append("G")
            elif (x, y) in game.dots:
                line.append(".")
            else:
                line.append(game.maze[y][x] if game.maze[y][x] == "#" else " ")
        rows.append("".join(line))
    return "\n".join(rows)


def describe_actions(game):
    """One line per legal action: steps to nearest dot / nearest ghost after moving there."""
    ghost_set = set(game.ghosts)
    out = {}
    for a in game.legal_actions():
        n = game.neighbor(game.pac, a)
        d = distances(game, n)
        dot = min((d[p] for p in game.dots if p in d), default=None)
        gh = min((d[g] for g in ghost_set if g in d), default=None)
        txt = f"move {a}: "
        txt += "eats a dot, " if n in game.dots else ""
        txt += f"nearest dot {dot} steps" if dot is not None else "no dots reachable"
        txt += f", nearest ghost {gh} steps" if gh is not None else ""
        out[a] = txt
    return out


def board(game):
    """Whole board as an N*M char matrix: # wall, . dot, P pacman, G ghost, space empty."""
    return "\n".join(game.render().split("\n")[:-1])


def build_matrix_request(game, model="nimble"):
    return {
        "model": model,
        "state": board(game),
        "questions": {"move": {
            "type": "choice",
            "instructions": "Pac-Man board (P=you, G=ghost, .=dot, #=wall). Which move is best?",
            "criteria": {a: None for a in game.legal_actions()}}},
    }


def danger_facts(game):
    """Per legal action: (ghost steps to the target cell, eats a dot, nearest dot steps avoiding ghost-adjacent cells)."""
    gmaps = [distances(game, g) for g in game.ghosts]
    near = frozenset(c for m in gmaps for c, d in m.items() if d <= 1)
    out = {}
    for a in game.legal_actions():
        n = game.neighbor(game.pac, a)
        gd = min(m.get(n, 99) for m in gmaps)
        if gd <= 1:
            out[a] = (gd, False, None)
            continue
        d = distances(game, n, near)
        dot = min((d[p] for p in game.dots if p in d), default=None)
        out[a] = (gd, n in game.dots, dot)
    return out


def describe_danger(game):
    """Per legal action: a short label led by DEADLY / risky / safe, then dot info.
    Ghost distance is measured to the target cell; dot distance avoids cells next to a ghost."""
    out = {}
    for a, (gd, eats, dot) in danger_facts(game).items():
        if gd <= 1:
            out[a] = "DEADLY: ghost " + ("on this cell" if gd == 0 else "adjacent")
            continue
        parts = ["risky, ghost 2 steps away" if gd == 2 else "safe"]
        parts.append("eats a dot" if eats else
                     f"nearest dot {dot} steps" if dot is not None else "no safe dot path")
        out[a] = "; ".join(parts)
    return out


def describe_danger_text(game):
    """Same facts as describe_danger, one complete sentence per direction."""
    out = {}
    for a, (gd, eats, dot) in danger_facts(game).items():
        if gd <= 1:
            out[a] = f"Moving {a}: a ghost is " + ("already on that cell" if gd == 0 else "right next to that cell") + ", so you would be caught."
            continue
        head = f"Moving {a}: " + ("a ghost is two steps away, which is risky" if gd == 2 else "it is safe")
        tail = ("and it eats a dot" if eats else
                f"and the nearest dot is {dot} steps away" if dot is not None else "and there is no safe path to a dot")
        out[a] = f"{head}, {tail}."
    return out


def build_danger_text_request(game, model="nimble"):
    """D2: D's facts as sentences; the instruction ends with a question that asks for the decision."""
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option describes what happens if you move that way. Pick the move that is safe and "
                                "has the nearest dot, never a move where you would be caught, and avoid risky moves "
                                "unless nothing is safe. Which move do you pick?",
                "criteria": describe_danger_text(game)}}}


DANGER_RULES = "Pac-Man. Eat all dots, avoid ghosts."
DANGER_ASK = ("Which move is best? Never pick DEADLY. Avoid risky unless nothing is safe. "
              "Otherwise pick the move with the nearest dot.")


def build_danger_request(game, model="nimble", with_view=True):
    state = {"rules": DANGER_RULES}
    if with_view:
        state["view"] = local_view(game)
    state["dots_left"] = str(len(game.dots))
    return {"model": model, "state": state,
            "questions": {"move": {"type": "choice", "instructions": DANGER_ASK,
                                   "criteria": describe_danger(game)}}}


def build_danger_min_request(game, model="nimble"):
    return build_danger_request(game, model, with_view=False)


COORD_DOT_RADIUS = 5  # list only dots within this Manhattan radius


def manhattan(game, a, b):
    dx = abs(a[0] - b[0])
    return min(dx, game.w - dx) + abs(a[1] - b[1])


RAY_NEAR = 3  # a ghost on the ray within this many cells counts as "near"


def ray(game, action):
    """Walk straight from pacman until a wall: (any dot ahead, steps to the first ghost or None)."""
    pos, dot, ghost = game.pac, False, None
    for k in range(1, game.w + 1):
        pos = game.neighbor(pos, action)
        if pos is None:
            break
        dot = dot or pos in game.dots
        if ghost is None and pos in game.ghosts:
            ghost = k
    return dot, ghost


def describe_rays(game):
    out = {}
    for a in game.legal_actions():
        dot, ghost = ray(game, a)
        out[a] = ", ".join(["dot" if dot else "no dot",
                            "no ghost" if ghost is None else "ghost near" if ghost <= RAY_NEAR else "ghost far"])
    return out


def build_rays_request(game, model="nimble"):
    """F1: one yes/no style summary per direction (straight line of sight). No distances, no map."""
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option describes what is straight ahead in that direction. "
                                "Which move is best? Go toward dots, never toward a near ghost.",
                "criteria": describe_rays(game)}}}


def describe_rays_text(game):
    """Same line-of-sight facts as describe_rays, written as one complete sentence per direction."""
    out = {}
    for a in game.legal_actions():
        dot, ghost = ray(game, a)
        g = ("no ghost is in sight" if ghost is None else
             "a ghost is close ahead" if ghost <= RAY_NEAR else "a ghost is far ahead")
        out[a] = f"Moving {a}: there is {'a dot' if dot else 'no dot'} ahead, and {g}."
    return out


def build_rays_text_request(game, model="nimble"):
    """F2: F1's information, each direction as a natural sentence instead of word fragments."""
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option describes what you would find by moving that way. "
                                "Pick the move that heads toward a dot, and never toward a close ghost.",
                "criteria": describe_rays_text(game)}}}


SIDE = {"up": ("left", "right"), "down": ("left", "right"), "left": ("up", "down"), "right": ("up", "down")}


def side_ghost(game, action):
    """Is a ghost in a cell directly beside the target cell (a side passage)? A plain adjacency lookup."""
    n = game.neighbor(game.pac, action)
    return any((c := game.neighbor(n, d)) is not None and c in game.ghosts for d in SIDE[action])


SIDE_REACH = 3  # how far down a side passage to look


def side_ray(game, action):
    """Steps from the target cell to the nearest ghost along either side passage (looking up to SIDE_REACH cells), or None.
    A wall right beside the target means no side passage, so a ghost in a parallel corridor is never reported."""
    n = game.neighbor(game.pac, action)
    best = None
    for d in SIDE[action]:
        pos = n
        for k in range(1, SIDE_REACH + 1):
            pos = game.neighbor(pos, d)
            if pos is None:
                break
            if pos in game.ghosts:
                best = k if best is None else min(best, k)
                break
    return best


def describe_rays_side(game):
    """Compact signature of the F5 facts (used by the no-model controls and the information ceiling)."""
    return {a: t + (", side ghost" if side_ghost(game, a) else "") for a, t in describe_rays(game).items()}


def toward_nearest_dot(game, action):
    """Does this move reduce the (wrapped Manhattan) distance to the nearest dot? Walls are ignored on purpose."""
    if not game.dots:
        return False
    near = min(manhattan(game, p, game.pac) for p in game.dots)
    n = game.neighbor(game.pac, action)
    return any(manhattan(game, p, game.pac) == near and manhattan(game, p, n) < near for p in game.dots)


def describe_rays_side_dots_text(game):
    out = {}
    for a, text in describe_rays_side_text(game).items():
        way = "toward" if toward_nearest_dot(game, a) else "not toward"
        out[a] = text[:-1] + f"; the nearest dot is {way} that way."
    return out


def build_rays_side_dots_request(game, model="nimble"):
    """F6: F5 plus, per direction, whether that move heads toward the nearest dot (Manhattan, walls ignored)."""
    req = build_rays_side_request(game, model)
    q = req["questions"]["move"]
    q["criteria"] = describe_rays_side_dots_text(game)
    q["instructions"] = ("Each option describes what you would find by moving that way. "
                         "Never pick a move toward a close ghost or a ghost in a side passage. "
                         "Otherwise prefer a dot straight ahead, and if there is none, the move toward the nearest dot. "
                         "Which move do you pick?")
    return req


def describe_rays_side_text(game):
    out = {}
    for a in game.legal_actions():
        dot, ghost = ray(game, a)
        g = ("no ghost is in sight" if ghost is None else
             "a ghost is close ahead" if ghost <= RAY_NEAR else "a ghost is far ahead")
        side = ("a ghost is in a side passage right next to that cell" if side_ghost(game, a)
                else "the side passages are clear")
        out[a] = f"Moving {a}: there is {'a dot' if dot else 'no dot'} ahead, {g}, and {side}."
    return out


def describe_rays_grade_text(game):
    """F7: like F5, but an option that leads next to a ghost (on the straight line within 2 cells, or in a side passage)
    is stated plainly as one that will get you caught, with no dot information to lure the model."""
    out = {}
    for a in game.legal_actions():
        dot, ghost = ray(game, a)
        if side_ghost(game, a) or (ghost is not None and ghost <= 2):
            out[a] = f"Moving {a}: a ghost is right there and will catch you."
            continue
        g = ("no ghost is in sight" if ghost is None else
             "a ghost is a few cells ahead" if ghost <= RAY_NEAR else "a ghost is far ahead")
        out[a] = f"Moving {a}: there is {'a dot' if dot else 'no dot'} ahead, {g}, and the side passages are clear."
    return out


def build_rays_grade_request(game, model="nimble"):
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option describes what you would find by moving that way. "
                                "Never pick an option where a ghost will catch you. "
                                "Otherwise pick the move that heads toward a dot. Which move do you pick?",
                "criteria": describe_rays_grade_text(game)}}}


def build_rays_side_request(game, model="nimble"):
    """F5: F4 plus the ghost-in-a-side-passage fact, aimed at the blind spot found in E14/E18."""
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option describes what you would find by moving that way. "
                                "Pick the move that heads toward a dot, and never toward a close ghost "
                                "or a ghost in a side passage. Which move do you pick?",
                "criteria": describe_rays_side_text(game)}}}


def build_rays_text_q_request(game, model="nimble"):
    """F3: F2's sentences, and the instruction ends with a question that asks for the decision."""
    req = build_rays_text_request(game, model)
    req["questions"]["move"]["instructions"] = (
        "Each option describes what you would find by moving that way. "
        "Moving toward a dot is good, and moving toward a close ghost is bad. "
        "Which move should you make?")
    return req


def build_rays_text_q2_request(game, model="nimble"):
    """F4: exactly F2's instruction, plus a closing question (isolates the effect of ending on a question)."""
    req = build_rays_text_request(game, model)
    req["questions"]["move"]["instructions"] += " Which move do you pick?"
    return req


def describe_neighbors(game):
    """N1: only the adjacent cell in each legal direction: dot / ghost / empty."""
    out = {}
    for a in game.legal_actions():
        n = game.neighbor(game.pac, a)
        out[a] = "ghost" if n in game.ghosts else "dot" if n in game.dots else "empty"
    return out


def build_neighbors_request(game, model="nimble"):
    return {"model": model, "state": {"game": "Pac-Man"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Each option is what is in the next cell in that direction. "
                                "Which move is best? Take dots, never step onto a ghost.",
                "criteria": describe_neighbors(game)}}}


def rel_phrase(game, src, dst):
    """'3 right 2 up' style offset from src to dst (shortest way around the tunnel)."""
    dx = (dst[0] - src[0] + game.w // 2) % game.w - game.w // 2
    dy = dst[1] - src[1]
    parts = ([f"{dx} right"] if dx > 0 else [f"{-dx} left"] if dx < 0 else []) + \
            ([f"{dy} down"] if dy > 0 else [f"{-dy} up"] if dy < 0 else [])
    return " ".join(parts) or "here"


NEAR_DOTS = 6


def build_coords_words_request(game, model="nimble"):
    """L1w: the same information as L1 but as relative directions in words (no BFS, no labels).
    Ghosts and dots are listed nearest-first by Manhattan distance."""
    ghosts = sorted(game.ghosts, key=lambda g: manhattan(game, g, game.pac))
    dots = sorted((p for p in game.dots if manhattan(game, p, game.pac) <= COORD_DOT_RADIUS),
                  key=lambda p: manhattan(game, p, game.pac))[:NEAR_DOTS]
    return {"model": model,
            "state": {"ghosts": "; ".join(rel_phrase(game, game.pac, g) for g in ghosts),
                      "dots": "; ".join(rel_phrase(game, game.pac, p) for p in dots) or "none nearby"},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Ghost and dot positions are given relative to you, nearest first. "
                                "Which move is best? Eat dots, never move next to a ghost.",
                "criteria": {a: None for a in game.legal_actions()}}}}


def build_coords_request(game, model="nimble"):
    """L1: raw coordinates only. No BFS distances, no safe/deadly labels, no map."""
    near = sorted(p for p in game.dots if manhattan(game, p, game.pac) <= COORD_DOT_RADIUS)
    return {"model": model,
            "state": {"pacman": list(game.pac), "ghosts": [list(g) for g in game.ghosts],
                      "dots_nearby": [list(p) for p in near], "dots_left": len(game.dots)},
            "questions": {"move": {
                "type": "choice",
                "instructions": "Coordinates are [x, y]; x grows to the right, y grows downward. "
                                "Which move is best? Eat dots, never move next to a ghost.",
                "criteria": {a: None for a in game.legal_actions()}}}}


def build_request(game, model="nimble"):
    return {
        "model": model,
        "state": {"rules": RULES, "view": local_view(game),
                  "dots_left": str(len(game.dots)), "lives": str(game.lives)},
        "questions": {"move": {
            "type": "choice",
            "instructions": "Which move is best? Prefer eating dots, never move toward a close ghost.",
            "criteria": describe_actions(game)}},
    }


FORMATS = {"text": build_request, "matrix": build_matrix_request,
           "coords": build_coords_request, "coords-words": build_coords_words_request, "rays": build_rays_request, "rays-text": build_rays_text_request, "rays-text-q": build_rays_text_q_request, "rays-text-q2": build_rays_text_q2_request, "rays-side": build_rays_side_request, "rays-grade": build_rays_grade_request, "rays-side-dots": build_rays_side_dots_request, "neighbors": build_neighbors_request, "danger": build_danger_request, "danger-text": build_danger_text_request, "danger-min": build_danger_min_request}


class NimbleAgent:
    def __init__(self, base_url=DEFAULT_URL, model="nimble", timeout=120, fmt="text"):
        self.build = FORMATS[fmt]
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.model, self.timeout = model, timeout
        self.last = None
        self.last_query = None  # the request of the last decision (without the model name), for the logs
        self.latencies = []

    def query(self, payload):
        req = urllib.request.Request(self.url, json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)

    def __call__(self, game, rng=None):
        t0 = time.perf_counter()
        req = self.build(game, self.model)
        self.last_query = {k: v for k, v in req.items() if k != "model"}
        ans = self.query(req)["answers"]["move"]
        ms = round((time.perf_counter() - t0) * 1000)
        self.latencies.append(ms)
        legal = game.legal_actions()
        probs = ans.get("probabilities", {})
        choice = ans["choice"]
        if choice not in legal:  # defensive: fall back to best legal option
            choice = max(legal, key=lambda a: probs.get(a, 0))
        self.last = {"choice": choice, "probabilities": probs,
                     "confidence": ans.get("confidence"), "ms": ms}
        return choice
