"""Check connectivity/latency: python -m pacman.probe [--base-url URL] [-n 5]"""
import argparse
import time
import urllib.error

from .game import Game
from .nimble import DEFAULT_URL, NimbleAgent, build_request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_URL)
    ap.add_argument("--model", default="nimble")
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    agent, game = NimbleAgent(a.base_url, a.model), Game()
    print("request state:\n" + build_request(game)["state"]["view"])
    for i in range(a.n):
        t0 = time.perf_counter()
        try:
            action = agent(game)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code} from {agent.url} (Ollama >= 0.35 and `ollama pull nimble` needed?)")
        except urllib.error.URLError as e:
            raise SystemExit(f"cannot reach {agent.url}: {e.reason}")
        print(f"#{i+1} {action:5s} {(time.perf_counter()-t0)*1000:7.0f} ms  {agent.last['probabilities']}")


if __name__ == "__main__":
    main()
