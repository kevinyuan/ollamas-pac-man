"""Run a game with an agent: python -m pacman.run [--agent bfs|random] [--seed N] [--ascii] [--log out.json]"""
import argparse
import json
import random

from .agents import bfs_agent, random_agent
from .game import GHOST_STARTS, PAC_START, Game
from .nimble import DEFAULT_URL, NimbleAgent

AGENTS = {"bfs": bfs_agent, "random": random_agent, "nimble": None}


def play(agent, seed=0, max_steps=500, on_step=None):
    game = Game(seed=seed, max_steps=max_steps)
    rng = random.Random(seed + 1)
    log = []
    while not game.over:
        action = agent(game, rng)
        caught = game.step(action)
        pac, ghosts = game.collision if caught else (game.pac, game.ghosts)  # show the catch itself
        r = getattr(agent, "last", None) or {"choice": action}
        entry = {"p": list(pac), "g": [list(g) for g in ghosts], "r": r}
        if "ms" in r:
            entry["ms"] = r["ms"]
        if getattr(agent, "last_query", None):
            entry["q"] = agent.last_query
        if caught:
            entry["c"] = 1
        log.append(entry)
        if on_step:
            on_step(game)
    return game, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=AGENTS, default="bfs")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--base-url", default=DEFAULT_URL, help="Ollama URL for --agent nimble")
    ap.add_argument("--model", default="nimble")
    ap.add_argument("--fmt", choices=["text", "matrix", "danger-text", "coords", "coords-words", "rays", "rays-text", "rays-text-q", "rays-text-q2", "rays-side", "rays-grade", "rays-side-dots", "neighbors", "danger", "danger-min"], default="text", help="state format for --agent nimble")
    ap.add_argument("--max-steps", type=int, default=500)
    ap.add_argument("--ascii", action="store_true", help="print every frame")
    ap.add_argument("--log", help="write JSON move log here")
    a = ap.parse_args()
    agent = NimbleAgent(a.base_url, a.model, fmt=a.fmt) if a.agent == "nimble" else AGENTS[a.agent]
    game, log = play(agent, a.seed, a.max_steps,
                     (lambda g: print(g.render(), "\n")) if a.ascii else None)
    print(game.render())
    print("WON" if game.won else "LOST" if game.lives <= 0 else "TIMEOUT")
    if getattr(agent, "latencies", None):
        lat = sorted(agent.latencies)
        print(f"latency ms: mean={sum(lat)/len(lat):.0f} p50={lat[len(lat)//2]} max={lat[-1]}")
    if a.log:
        with open(a.log, "w") as f:
            json.dump({"model": a.model if a.agent == "nimble" else a.agent,
                       "fmt": a.fmt if a.agent == "nimble" else None, "maze": game.maze, "start": {"pac": list(PAC_START), "ghosts": [list(g) for g in GHOST_STARTS]}, "moves": log}, f)


if __name__ == "__main__":
    main()
