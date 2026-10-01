/* Pac-Man engine: a JS port of pacman/game.py (same maze and rules). Coordinates are [x, y] = [column, row].
 * The ghosts use Math.random, so runs are not seed-for-seed identical to the Python engine. */
(function (root) {
  "use strict";
  var MAZE = [
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
    "###################"
  ];
  var PAC_START = [9, 15], GHOST_STARTS = [[9, 7], [7, 7], [11, 7]];
  var DIRS = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
  var OPPOSITE = { up: "down", down: "up", left: "right", right: "left" };
  var key = function (p) { return p[0] + "," + p[1]; };
  var same = function (a, b) { return a[0] === b[0] && a[1] === b[1]; };

  // opts: rng (default Math.random), lives (3), startDot (false: no dot under the start cell, so the player
  // does not have to come back for it; the Python engine keeps it, pass true for exact parity).
  function Game(opts) {
    opts = opts || {};
    this.rng = opts.rng || Math.random;
    this.maze = MAZE;
    this.h = MAZE.length;
    this.w = MAZE[0].length;
    this.lives = opts.lives || 3;
    this.dots = {};
    for (var y = 0; y < this.h; y++)
      for (var x = 0; x < this.w; x++)
        if (MAZE[y][x] === "." && (opts.startDot || x !== PAC_START[0] || y !== PAC_START[1])) this.dots[x + "," + y] = true;
    this.totalDots = Object.keys(this.dots).length;
    this.score = 0;
    this.steps = 0;
    this.caught = false;
    this.collision = null;  // {pac, ghosts} at the moment of the last catch
    this.resetPositions();
  }
  Game.prototype.resetPositions = function () {
    this.pac = PAC_START.slice();
    this.ghosts = GHOST_STARTS.map(function (g) { return g.slice(); });
    this.ghostDir = this.ghosts.map(function () { return null; });
  };
  Game.prototype.neighbor = function (pos, action) {
    var d = DIRS[action], x = pos[0] + d[0], y = pos[1] + d[1];
    if (y < 0 || y >= this.h) return null;
    x = (x % this.w + this.w) % this.w;
    return this.maze[y][x] === "#" ? null : [x, y];
  };
  Game.prototype.legalActions = function (pos) {
    var self = this, p = pos || this.pac;
    return Object.keys(DIRS).filter(function (a) { return self.neighbor(p, a); });
  };
  Game.prototype.dotsLeft = function () { return Object.keys(this.dots).length; };
  Object.defineProperty(Game.prototype, "won", { get: function () { return this.dotsLeft() === 0; } });
  Object.defineProperty(Game.prototype, "over", { get: function () { return this.won || this.lives <= 0; } });

  Game.prototype._moveGhost = function (i) {
    var self = this, pos = this.ghosts[i], prev = this.ghostDir[i], options = this.legalActions(pos);
    if (prev && options.length > 1) options = options.filter(function (a) { return a !== OPPOSITE[prev]; });
    if (this.rng() < 0.6) {  // chase: greedy by wrapped Manhattan distance to pacman
      var dist = function (a) {
        var n = self.neighbor(pos, a), dx = Math.abs(n[0] - self.pac[0]);
        return Math.min(dx, self.w - dx) + Math.abs(n[1] - self.pac[1]);
      };
      var best = Math.min.apply(null, options.map(dist));
      options = options.filter(function (a) { return dist(a) === best; });
    }
    var action = options[Math.floor(this.rng() * options.length)];
    this.ghostDir[i] = action;
    this.ghosts[i] = this.neighbor(pos, action);
  };

  // One turn: pacman moves (action null = stays put, e.g. blocked by a wall), then every ghost moves one cell.
  Game.prototype.step = function (action) {
    if (this.over) throw new Error("game is over");
    var oldPac = this.pac, oldGhosts = this.ghosts.slice(), nxt = this.pac;
    if (action) {
      nxt = this.neighbor(this.pac, action);
      if (!nxt) throw new Error("illegal action " + action + " at " + this.pac);
    }
    this.pac = nxt;
    this.steps++;
    if (this.dots[key(nxt)]) { delete this.dots[key(nxt)]; this.score += 10; }
    for (var i = 0; i < this.ghosts.length; i++) this._moveGhost(i);
    var self = this;
    this.caught = this.ghosts.some(function (g, i) {
      return same(g, self.pac) || (same(g, oldPac) && same(oldGhosts[i], self.pac));
    });
    this.collision = this.caught ? { pac: this.pac.slice(), ghosts: this.ghosts.map(function (g) { return g.slice(); }) } : null;
    if (this.caught) {
      this.lives--;
      this.score -= 50;
      this.resetPositions();
    }
    return this.caught;
  };

  var api = { Game: Game, MAZE: MAZE, PAC_START: PAC_START, GHOST_STARTS: GHOST_STARTS, DIRS: DIRS, OPPOSITE: OPPOSITE };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PacGame = api;
})(this);
