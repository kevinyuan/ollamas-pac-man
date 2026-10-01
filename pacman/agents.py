from collections import deque

from .game import DIRS


def random_agent(game, rng):
    return rng.choice(game.legal_actions())


def bfs_first_step(game, start, is_goal, blocked=frozenset()):
    """First action of the shortest path from start to a goal cell, or None."""
    queue = deque([(start, None)])
    seen = {start}
    while queue:
        pos, first = queue.popleft()
        if pos != start and is_goal(pos):
            return first
        for a in DIRS:
            n = game.neighbor(pos, a)
            if n and n not in seen and n not in blocked:
                seen.add(n)
                queue.append((n, first or a))
    return None


def bfs_agent(game, rng=None):
    """Nearest-dot BFS that treats cells within 2 steps of a ghost as blocked."""
    danger = set(game.ghosts)
    for _ in range(2):
        danger |= {n for g in danger for a in DIRS if (n := game.neighbor(g, a))}
    danger.discard(game.pac)
    for blocked in (danger, set(game.ghosts), set()):
        a = bfs_first_step(game, game.pac, lambda p: p in game.dots, frozenset(blocked))
        if a:
            return a
    return game.legal_actions()[0]
