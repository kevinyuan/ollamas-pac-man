// Rules of the JS engine (web/game.js) must match pacman/game.py. Run: node tests/test_game_js.js
const assert = require("assert");
const { Game, MAZE, PAC_START, GHOST_STARTS } = require("../web/game.js");

function seeded(seed) {  // mulberry32
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const tests = {
  "maze is rectangular and starts are open"() {
    assert.strictEqual(new Set(MAZE.map(r => r.length)).size, 1);
    assert.strictEqual(MAZE.length, 21);
    [PAC_START, ...GHOST_STARTS].forEach(p => assert.notStrictEqual(MAZE[p[1]][p[0]], "#"));
  },
  "dot counts: 150 by default, 151 with the start dot like Python"() {
    assert.strictEqual(new Game().totalDots, 150);
    assert.strictEqual(new Game({ startDot: true }).totalDots, 151);
  },
  "legal actions at the start are left/right, illegal throws"() {
    const g = new Game();
    assert.deepStrictEqual(g.legalActions().sort(), ["left", "right"]);
    assert.throws(() => g.step("down"));
  },
  "tunnel wraps"() {
    const g = new Game();
    assert.deepStrictEqual(g.neighbor([0, 9], "left"), [18, 9]);
    assert.deepStrictEqual(g.neighbor([18, 9], "right"), [0, 9]);
  },
  "eating a dot scores 10"() {
    const g = new Game({ rng: seeded(1) });
    g.pac = [8, 15]; g.dots = { "7,15": true, "1,1": true }; g.ghosts = [[1, 19], [1, 19], [1, 19]];
    g.step("left");
    assert.strictEqual(g.score, 10);
    assert.deepStrictEqual(Object.keys(g.dots), ["1,1"]);
  },
  "a catch costs a life and resets positions"() {
    const g = new Game({ rng: seeded(1) });
    g.pac = [8, 15]; g.ghosts = [[7, 15], [1, 19], [1, 19]];
    g._moveGhost = function () {};  // ghosts stay put, so pacman walks onto the ghost's cell
    assert.strictEqual(g.step("left"), true);
    assert.strictEqual(g.lives, 2);
    assert.deepStrictEqual(g.pac, PAC_START);
    assert.deepStrictEqual(g.ghosts, GHOST_STARTS);
    assert.deepStrictEqual(g.collision.pac, [7, 15]);
    assert.strictEqual(g.score, 10 - 50);  // the dot under the catch is eaten first
  },
  "swapping places with a ghost is a catch"() {
    const g = new Game({ rng: () => 0.99 });  // ghosts never chase, always take the last option
    g.pac = [8, 15]; g.ghosts = [[7, 15], [1, 19], [1, 19]]; g.ghostDir = [null, null, null];
    // pacman moves left into (7,15); the ghost at (7,15) leaves to the right (8,15) => swap
    g._moveGhost = function (i) { if (i === 0) this.ghosts[0] = [8, 15]; };
    assert.strictEqual(g.step("left"), true);
  },
  "blocked (null action) keeps pacman in place but the turn is taken"() {
    const g = new Game({ rng: seeded(2) });
    const before = g.steps;
    g.step(null);
    assert.deepStrictEqual(g.pac, PAC_START);
    assert.strictEqual(g.steps, before + 1);
  },
  "game over after the last life, and stepping afterwards throws"() {
    const g = new Game({ rng: seeded(1), lives: 1 });
    g.pac = [8, 15]; g.ghosts = [[7, 15], [1, 19], [1, 19]];
    g._moveGhost = function () {};
    g.step("left");
    assert.ok(g.over);
    assert.throws(() => g.step("left"));
  },
  "ghosts never enter walls (random play, 3000 steps)"() {
    const rng = seeded(7);
    let g = new Game({ rng, lives: 1000 });
    for (let i = 0; i < 3000 && !g.over; i++) {
      const legal = g.legalActions();
      g.step(legal[Math.floor(rng() * legal.length)]);
      g.ghosts.forEach(([x, y]) => assert.notStrictEqual(MAZE[y][x], "#"));
    }
  },
  "deterministic with a seeded rng"() {
    const run = () => { const rng = seeded(5), g = new Game({ rng, lives: 1000 }); const out = [];
      for (let i = 0; i < 200; i++) { const l = g.legalActions(); g.step(l[Math.floor(rng() * l.length)]); out.push(g.pac.join(), g.ghosts.join()); } return out.join("|"); };
    assert.strictEqual(run(), run());
  },
  "clearing every dot wins"() {
    const g = new Game({ rng: seeded(1) });
    g.pac = [8, 15]; g.dots = { "7,15": true }; g.ghosts = [[1, 19], [1, 19], [1, 19]];
    g.step("left");
    assert.ok(g.won && g.over);
  },
};
let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { fn(); console.log("ok   " + name); } catch (e) { failed++; console.log("FAIL " + name + "\n     " + e.message); }
}
process.exit(failed ? 1 : 0);
