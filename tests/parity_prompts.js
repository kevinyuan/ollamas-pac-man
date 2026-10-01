// Compare the requests built by web/prompts.js with the ones pacman/nimble.py built for the same states.
// Usage: node tests/parity_prompts.js cases.json
const assert = require("assert");
const fs = require("fs");
const { Game } = require("../web/game.js");
const P = require("../web/prompts.js");

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let n = 0;
for (const c of cases) {
  const g = new Game({ startDot: true });
  g.pac = c.pac; g.ghosts = c.ghosts; g.dots = {};
  c.dots.forEach(d => { g.dots[d[0] + "," + d[1]] = true; });
  for (const [fmt, expected] of Object.entries(c.expected)) {
    assert.deepStrictEqual(P.build(fmt, g, "nimble"), expected, `format ${fmt} differs for pac=${c.pac} ghosts=${JSON.stringify(c.ghosts)}`);
    n++;
  }
}
console.log(`ok: ${n} requests identical (${cases.length} states)`);
