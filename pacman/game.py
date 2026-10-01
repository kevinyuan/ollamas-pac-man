"""Headless Pac-Man engine. Coordinates are (x, y) = (column, row)."""
import random

MAZE = [
    "###################",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "    .  #   #  .    ",
    "####.# ##### #.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#..#...........#..#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]
PAC_START = (9, 15)
GHOST_STARTS = [(9, 7), (7, 7), (11, 7)]
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


class Game:
    def __init__(self, seed=0, maze=None, max_steps=500, lives=3):
        self.maze = maze or MAZE
        self.h, self.w = len(self.maze), len(self.maze[0])
        self.rng = random.Random(seed)
        self.max_steps = max_steps
        self.lives = lives
        self.dots = {(x, y) for y, row in enumerate(self.maze)
                     for x, c in enumerate(row) if c == "."}
        self.total_dots = len(self.dots)
        self.score = 0
        self.steps = 0
        self.pac = PAC_START
        self.ghosts = list(GHOST_STARTS)
        self.ghost_dir = [None] * len(self.ghosts)
        self.caught = False  # whether the last step cost a life
        self.collision = None  # (pac, ghosts) positions at the moment of the last catch

    # --- geometry -------------------------------------------------------
    def neighbor(self, pos, action):
        """Cell reached from pos by action (wrapping horizontally), or None if wall/off-map."""
        dx, dy = DIRS[action]
        x, y = pos[0] + dx, pos[1] + dy
        if y < 0 or y >= self.h:
            return None
        x %= self.w
        return None if self.maze[y][x] == "#" else (x, y)

    def legal_actions(self, pos=None):
        pos = self.pac if pos is None else pos
        return [a for a in DIRS if self.neighbor(pos, a)]

    # --- state ----------------------------------------------------------
    @property
    def won(self):
        return not self.dots

    @property
    def over(self):
        return self.won or self.lives <= 0 or self.steps >= self.max_steps

    # --- dynamics -------------------------------------------------------
    def _move_ghost(self, i):
        pos, prev = self.ghosts[i], self.ghost_dir[i]
        options = self.legal_actions(pos)
        if prev and len(options) > 1:  # never reverse unless dead end
            options = [a for a in options if a != OPPOSITE[prev]]
        if self.rng.random() < 0.6:  # chase: greedy by wrapped Manhattan distance to pacman
            def dist(a):
                n = self.neighbor(pos, a)
                dx = abs(n[0] - self.pac[0])
                return min(dx, self.w - dx) + abs(n[1] - self.pac[1])
            best = min(dist(a) for a in options)
            options = [a for a in options if dist(a) == best]
        action = self.rng.choice(options)
        self.ghost_dir[i] = action
        self.ghosts[i] = self.neighbor(pos, action)

    def step(self, action):
        if self.over:
            raise RuntimeError("game is over")
        nxt = self.neighbor(self.pac, action)
        if nxt is None:
            raise ValueError(f"illegal action {action!r} at {self.pac}")
        old_pac, old_ghosts = self.pac, list(self.ghosts)
        self.pac = nxt
        self.steps += 1
        if nxt in self.dots:
            self.dots.discard(nxt)
            self.score += 10
        for i in range(len(self.ghosts)):
            self._move_ghost(i)
        # caught: same cell, or swapped places
        self.caught = any(
            g == self.pac or (g == old_pac and old_g == self.pac)
            for g, old_g in zip(self.ghosts, old_ghosts))
        self.collision = (self.pac, list(self.ghosts)) if self.caught else None
        if self.caught:
            self.lives -= 1
            self.score -= 50
            self.pac = PAC_START
            self.ghosts = list(GHOST_STARTS)
            self.ghost_dir = [None] * len(self.ghosts)
        return self.caught

    # --- rendering ------------------------------------------------------
    def render(self):
        rows = []
        for y, row in enumerate(self.maze):
            line = []
            for x, c in enumerate(row):
                if (x, y) == self.pac:
                    line.append("P")
                elif (x, y) in self.ghosts:
                    line.append("G")
                elif c == "." and (x, y) not in self.dots:
                    line.append(" ")
                else:
                    line.append(c)
            rows.append("".join(line))
        rows.append(f"score={self.score} lives={self.lives} dots={len(self.dots)} step={self.steps}")
        return "\n".join(rows)
