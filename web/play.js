/* Human play mode + tab switching. Needs board.js and game.js. */
(function () {
  "use strict";
  var fig = document.querySelector("[data-play]");
  if (!fig) return;
  var svg = fig.querySelector("[data-play-maze]"), statusEl = fig.querySelector("[data-play-status]");
  var el = function (n) { return fig.querySelector("[data-" + n + "]"); };
  var TICK = 170, CAUGHT_PAUSE = 1100;           // ms per turn (pacman and ghosts move one cell per turn)
  var KEYS = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", w: "up", s: "down", a: "left", d: "right", W: "up", S: "down", A: "left", D: "right" };
  var game, view, mode, dir, want, from, to, tStart, until, pausedAt, frame = 0, best = 0;

  try { best = +localStorage.getItem("pacman.best") || 0; } catch (e) {}
  var key = function (p) { return p[0] + "," + p[1]; };
  function snap() { return { pac: game.pac.slice(), ghosts: game.ghosts.map(function (g) { return g.slice(); }) }; }
  function setStatus(t, state) { statusEl.textContent = t; statusEl.setAttribute("data-state", state || ""); }

  function stats() {
    el("score").textContent = game.score;
    el("lives").textContent = new Array(Math.max(0, game.lives) + 1).join("♥ ").trim() || "–";
    el("dots").textContent = game.dotsLeft();
    el("best").textContent = best;
  }
  function saveBest() {
    if (game.score > best) { best = game.score; try { localStorage.setItem("pacman.best", best); } catch (e) {} }
    stats();
  }

  function draw(now) {
    var k = Math.min(1, Math.max(0, (now - tStart) / TICK));
    PacBoard.drawPac(view, PacBoard.lerp(from.pac[0], to.pac[0], k), PacBoard.lerp(from.pac[1], to.pac[1], k), dir,
      mode === "running" || mode === "caught" ? Math.abs(Math.sin(k * Math.PI)) : .8);
    to.ghosts.forEach(function (g, j) {
      PacBoard.place(view.ghosts[j], PacBoard.lerp(from.ghosts[j][0], g[0], k), PacBoard.lerp(from.ghosts[j][1], g[1], k));
    });
  }

  function advance(now) {
    var legal = game.legalActions();
    if (want && legal.indexOf(want) >= 0) dir = want;
    var prev = snap(), caught = game.step(legal.indexOf(dir) >= 0 ? dir : null);
    var at = caught ? game.collision.pac : game.pac, d = view.dots[key(at)];
    if (d && !game.dots[key(at)]) d.style.display = "none";
    from = prev;
    to = caught ? { pac: game.collision.pac, ghosts: game.collision.ghosts } : snap();
    tStart = now;
    stats();
    if (caught) {
      if (game.over) { mode = "over"; setStatus("Game over · press Enter to play again", "done"); saveBest(); return; }
      mode = "caught"; until = now + TICK + CAUGHT_PAUSE; setStatus("Caught! " + game.lives + (game.lives === 1 ? " life" : " lives") + " left");
    } else if (game.won) {
      mode = "over"; setStatus("You cleared the maze! · press Enter to play again", "done"); saveBest();
    }
  }

  function loop(now) {
    frame = requestAnimationFrame(loop);
    if (mode === "running") {
      if (now - tStart >= TICK) advance(now);
      draw(now);
    } else if (mode === "caught") {
      if (now >= until) {
        from = to = snap(); tStart = now; want = null; dir = "left"; mode = "running"; setStatus("Go!");
        draw(now);
      } else draw(now);
    } else if (mode === "over") draw(now);
  }

  function newGame() {
    game = new PacGame.Game();
    view = PacBoard.build(svg, { maze: game.maze, start: { pac: PacGame.PAC_START, ghosts: PacGame.GHOST_STARTS } });
    mode = "ready"; dir = "left"; want = null; from = to = snap(); tStart = performance.now();
    PacBoard.drawPac(view, game.pac[0], game.pac[1], dir, .8);
    to.ghosts.forEach(function (g, j) { PacBoard.place(view.ghosts[j], g[0], g[1]); });
    stats();
    setStatus("Press an arrow key to start");
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(loop);
  }

  function pause() {
    if (mode === "running") { mode = "paused"; pausedAt = performance.now(); setStatus("Paused · press Space to resume"); }
  }
  function resume() {
    if (mode === "paused") { tStart += performance.now() - pausedAt; mode = "running"; setStatus("Go!"); }
  }

  function steer(d) {
    if (mode === "over") return;
    want = d;
    if (mode === "ready") { mode = "running"; dir = d; tStart = performance.now(); setStatus("Go!"); }
    else if (mode === "paused") resume();
  }

  document.addEventListener("keydown", function (e) {
    if (fig.hidden || e.metaKey || e.ctrlKey || e.altKey) return;
    if (KEYS[e.key]) { e.preventDefault(); steer(KEYS[e.key]); }
    else if (e.key === " " || e.key === "p" || e.key === "P") { e.preventDefault(); mode === "paused" ? resume() : pause(); }
    else if (e.key === "Enter" || e.key === "r" || e.key === "R") { e.preventDefault(); if (mode === "over" || e.key !== "Enter") newGame(); }
  });
  document.addEventListener("visibilitychange", function () { if (document.hidden) pause(); });
  el("play-restart").addEventListener("click", newGame);
  Array.prototype.forEach.call(fig.querySelectorAll("[data-dir]"), function (b) {
    b.addEventListener("click", function () { steer(b.getAttribute("data-dir")); });
  });
  var sx, sy;  // swipe on the board
  svg.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
  svg.addEventListener("touchend", function (e) {
    var t = e.changedTouches[0], dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    steer(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
  }, { passive: true });

  window.addEventListener("pactab", function (e) { if (e.detail !== "play") pause(); });

  newGame();
})();
