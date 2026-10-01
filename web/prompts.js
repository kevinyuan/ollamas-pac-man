/* Request builders for Nimble (/v1/systemone): a JS port of the matching functions in pacman/nimble.py.
 * tests/test_prompts_parity.py checks that both sides produce identical requests for the same game state.
 * `game` is a PacGame.Game (pac, ghosts, dots{"x,y": true}, w, neighbor, legalActions). */
(function (root) {
  "use strict";
  var RAY_NEAR = 3;
  var SIDE = { up: ["left", "right"], down: ["left", "right"], left: ["up", "down"], right: ["up", "down"] };
  var key = function (p) { return p[0] + "," + p[1]; };
  var hasGhost = function (game, p) { return game.ghosts.some(function (g) { return g[0] === p[0] && g[1] === p[1]; }); };
  var dotList = function (game) { return Object.keys(game.dots).map(function (k) { return k.split(",").map(Number); }); };

  function manhattan(game, a, b) {
    var dx = Math.abs(a[0] - b[0]);
    return Math.min(dx, game.w - dx) + Math.abs(a[1] - b[1]);
  }
  // Walk straight from pacman until a wall: whether a dot is on the way, and the steps to the first ghost.
  function ray(game, action) {
    var pos = game.pac, dot = false, ghost = null;
    for (var k = 1; k <= game.w; k++) {
      pos = game.neighbor(pos, action);
      if (pos === null) break;
      dot = dot || !!game.dots[key(pos)];
      if (ghost === null && hasGhost(game, pos)) ghost = k;
    }
    return { dot: dot, ghost: ghost };
  }
  function sideGhost(game, action) {
    var n = game.neighbor(game.pac, action);
    return SIDE[action].some(function (d) {
      var c = game.neighbor(n, d);
      return c !== null && hasGhost(game, c);
    });
  }
  function towardNearestDot(game, action) {
    var dots = dotList(game);
    if (!dots.length) return false;
    var near = Math.min.apply(null, dots.map(function (p) { return manhattan(game, p, game.pac); }));
    var n = game.neighbor(game.pac, action);
    return dots.some(function (p) { return manhattan(game, p, game.pac) === near && manhattan(game, p, n) < near; });
  }
  function ghostText(r) {
    return r.ghost === null ? "no ghost is in sight" : r.ghost <= RAY_NEAR ? "a ghost is close ahead" : "a ghost is far ahead";
  }
  function criteria(game, sentence) {
    var out = {};
    game.legalActions().forEach(function (a) { out[a] = sentence(a, ray(game, a)); });
    return out;
  }
  var dotText = function (r) { return r.dot ? "a dot" : "no dot"; };

  var BASE = "Each option describes what you would find by moving that way. ";
  function request(model, instructions, crit) {
    return { model: model, state: { game: "Pac-Man" },
      questions: { move: { type: "choice", instructions: instructions, criteria: crit } } };
  }

  var FORMATS = {
    "rays-text-q2": {
      name: "F4: straight-line view",
      note: "Per direction: is there a dot ahead, is a ghost in sight. No BFS.",
      build: function (game, model) {
        return request(model, BASE + "Pick the move that heads toward a dot, and never toward a close ghost. Which move do you pick?",
          criteria(game, function (a, r) { return "Moving " + a + ": there is " + dotText(r) + " ahead, and " + ghostText(r) + "."; }));
      }
    },
    "rays-side": {
      name: "F5: + side passages",
      note: "F4 plus: is a ghost in a side passage right next to the cell you would move into.",
      build: function (game, model) {
        return request(model, BASE + "Pick the move that heads toward a dot, and never toward a close ghost or a ghost in a side passage. Which move do you pick?",
          criteria(game, function (a, r) {
            var side = sideGhost(game, a) ? "a ghost is in a side passage right next to that cell" : "the side passages are clear";
            return "Moving " + a + ": there is " + dotText(r) + " ahead, " + ghostText(r) + ", and " + side + ".";
          }));
      }
    },
    "rays-grade": {
      name: "F7: plain 'will catch you'",
      note: "F5, but an option next to a ghost is stated plainly as one that gets you caught, with no dot information.",
      build: function (game, model) {
        return request(model, BASE + "Never pick an option where a ghost will catch you. Otherwise pick the move that heads toward a dot. Which move do you pick?",
          criteria(game, function (a, r) {
            if (sideGhost(game, a) || (r.ghost !== null && r.ghost <= 2)) return "Moving " + a + ": a ghost is right there and will catch you.";
            var g = r.ghost === null ? "no ghost is in sight" : r.ghost <= RAY_NEAR ? "a ghost is a few cells ahead" : "a ghost is far ahead";
            return "Moving " + a + ": there is " + dotText(r) + " ahead, " + g + ", and the side passages are clear.";
          }));
      }
    },
    "rays-side-dots": {
      name: "F6: + nearest-dot hint",
      note: "F5 plus: does this move head toward the nearest dot (straight-line distance, walls ignored).",
      build: function (game, model) {
        return request(model, BASE + "Never pick a move toward a close ghost or a ghost in a side passage. " +
          "Otherwise prefer a dot straight ahead, and if there is none, the move toward the nearest dot. Which move do you pick?",
          criteria(game, function (a, r) {
            var side = sideGhost(game, a) ? "a ghost is in a side passage right next to that cell" : "the side passages are clear";
            var way = towardNearestDot(game, a) ? "toward" : "not toward";
            return "Moving " + a + ": there is " + dotText(r) + " ahead, " + ghostText(r) + ", and " + side + "; the nearest dot is " + way + " that way.";
          }));
      }
    }
  };

  var api = { FORMATS: FORMATS, build: function (format, game, model) { return FORMATS[format].build(game, model || "nimble"); } };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PacPrompts = api;
})(this);
