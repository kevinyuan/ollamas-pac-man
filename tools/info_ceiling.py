"""Information ceiling and rule-agent games. No model calls.

  PYTHONPATH=. python3 tools/info_ceiling.py

Part 1: for each input encoding, the best any policy that sees only that input could do at matching the
BFS agent = for every distinct input, always answer the BFS action that is most common for it (learned on
train games, scored on held-out games). Compare with the hand-written rule on the same input.
Part 2: the rule agents play whole games.
"""
import random
import statistics
from collections import Counter, defaultdict

from pacman.agents import bfs_agent, random_agent
from pacman.game import Game
from pacman.nimble import describe_danger, describe_neighbors, describe_rays, describe_rays_side
from pacman.run import play
from tools.offline_eval import ghost_dist, make_states, rule_f1, rule_f5, rule_l3, rule_n1

ENCODINGS = {
    "N1 adjacent cell": (describe_neighbors, rule_n1),
    "F1 rays": (describe_rays, rule_f1),
    "F5 rays+side": (describe_rays_side, rule_f5),
    "D BFS labels": (describe_danger, rule_l3),
}


def collect(seeds, eps=0.3, every=2):
    """States from epsilon-noisy BFS games (so ghosts come close)."""
    out = []
    for s in seeds:
        rng, g, r = random.Random(s), Game(seed=s, max_steps=400), random.Random(s + 1)
        t = 0
        while not g.over:
            if len(g.legal_actions()) >= 2 and t % every == 0:
                c = Game(seed=0)
                c.__dict__.update({k: (v.copy() if hasattr(v, "copy") else v) for k, v in g.__dict__.items()})
                c.ghosts = list(g.ghosts)
                out.append(c)
            g.step(rng.choice(g.legal_actions()) if rng.random() < eps else bfs_agent(g, r))
            t += 1
    return out


def sig(fn, g):
    return tuple(sorted(fn(g).items()))


def unsafe(g, a):
    return ghost_dist(g, a) <= 1


def main():
    train, test = collect(range(100, 160)), collect(range(200, 230))
    small, _ = make_states(60)
    print(f"train {len(train)} states, held-out {len(test)} states, original-60 {len(small)} states\n")
    print(f"{'input':18s} {'distinct':>8s} {'rule agree':>10s} {'ceiling agree':>13s} {'rule unsafe':>11s} {'ceiling unsafe':>14s} {'unseen':>7s}")
    for name, (fn, rule) in ENCODINGS.items():
        table = defaultdict(Counter)
        for g in train:
            table[sig(fn, g)][bfs_agent(g)] += 1
        best = {k: c.most_common(1)[0][0] for k, c in table.items()}

        def ceiling(g):
            return best.get(sig(fn, g)) or rule(g)

        def score(states, pol):
            return (statistics.mean(pol(g) == bfs_agent(g) for g in states),
                    statistics.mean(unsafe(g, pol(g)) for g in states))
        ra, ru = score(test, rule)
        ca, cu = score(test, ceiling)
        unseen = statistics.mean(sig(fn, g) not in best for g in test)
        print(f"{name:18s} {len(best):8d} {ra:10.0%} {ca:13.0%} {ru:11.0%} {cu:14.0%} {unseen:7.0%}")
        sa, _ = score(small, ceiling)
        sr, _ = score(small, rule)
        print(f"{'  on original 60':18s} {'':8s} {sr:10.0%} {sa:13.0%}")

    print("\nWhole games (seeds 1-20):")
    agents = {"BFS": bfs_agent, "RF rays rule": lambda g, r: rule_f1(g), "RF5 rays+side rule": lambda g, r: rule_f5(g), "R3 BFS-label rule": lambda g, r: rule_l3(g),
              "RN adjacent rule": lambda g, r: rule_n1(g), "random": random_agent}
    for name, ag in agents.items():
        res = [play(ag, seed=s)[0] for s in range(1, 21)]
        print(f"  {name:18s} mean score {statistics.mean(g.score for g in res):6.0f}  won {sum(g.won for g in res):2d}/20  "
              f"mean steps {statistics.mean(g.steps for g in res):4.0f}  mean dots left {statistics.mean(len(g.dots) for g in res):5.1f}")
    for s in (1, 2, 3):
        g = play(lambda g, r: rule_f1(g), seed=s)[0]
        print(f"  RF seed {s}: score {g.score}, dots left {len(g.dots)}, steps {g.steps}, lives {g.lives}")


if __name__ == "__main__":
    main()
