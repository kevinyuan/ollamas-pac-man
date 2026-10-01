(function () {
  "use strict";
  var fig = document.querySelector("[data-pacman]");
  var svg = fig.querySelector("[data-maze]"), out = fig.querySelector("[data-json]");
  var label = fig.querySelector("[data-move]"), note = fig.querySelector("[data-note]");
  var run = 0, frame = 0, inView = false, resume = null, view = null, io = null;

  var place = PacBoard.place, drawPac = PacBoard.drawPac, lerp = PacBoard.lerp;
  function build(game) { return PacBoard.build(svg, game); }

  // ---- side panels: the /v1/systemone request and response ------------------
  var queryEl = fig.querySelector("[data-query]");
  function panel(m) {
    out.innerHTML = PacPanels.answerHTML(m.r || {});
    queryEl.innerHTML = m.q ? PacPanels.queryHTML(m.q, m.r && m.r.choice)
      : PacPanels.muted("The request was not recorded for this run. Re-run it with --agent nimble to record it.");
  }
  function status(text) { label.textContent = text; }

  // ---- replay ------------------------------------------------------------
  function resetBoard(v) {
    Object.keys(v.dots).forEach(function (k) { v.dots[k].style.display = ""; });
    var s = v.game.start;
    return { pac: s.pac.slice(), ghosts: s.ghosts.map(function (g) { return g.slice(); }), lives: 3 };
  }
  function showFrame(v, s, dir) {
    s.ghosts.forEach(function (g, j) { place(v.ghosts[j], g[0], g[1]); });
    drawPac(v, s.pac[0], s.pac[1], dir || "left", .8);
  }
  function over(msg) { status(msg || "Game over"); fig.classList.remove("busy"); }

  function finish(v) {  // reduced motion: show the end state
    var moves = v.game.moves, s = resetBoard(v);
    moves.forEach(function (m) { var d = v.dots[m.p[0] + "," + m.p[1]]; if (d) d.style.display = "none"; });
    var last = moves[moves.length - 1];
    showFrame(v, { pac: last.p, ghosts: last.g }, last.r.choice);
    panel(last);
    over();
  }

  function play() {
    var v = view, id = ++run, moves = v.game.moves;
    cancelAnimationFrame(frame);
    resume = null;
    fig.classList.add("busy");
    if (!moves.length) return over("No moves");
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return finish(v);
    var s = resetBoard(v), i = 0, from, t0, dur, pause = 0;
    function begin(now) {
      from = { pac: s.pac.slice(), ghosts: s.ghosts.map(function (g) { return g.slice(); }) };
      dur = Math.min(600, Math.max(80, moves[i].ms || 120));  // recorded decision time, clamped
      panel(moves[i]);
      status("Move " + (i + 1) + " of " + moves.length);
      t0 = now;
    }
    function tick(now) {
      if (id !== run) return;
      if (!inView) {  // off screen: hold, and carry on from the same point when visible again
        resume = function (later) { t0 += later - now; if (pause) pause += later - now; tick(later); };
        return;
      }
      if (pause) {
        if (now < pause) { frame = requestAnimationFrame(tick); return; }
        pause = 0;
        s.pac = v.game.start.pac.slice();
        s.ghosts = v.game.start.ghosts.map(function (g) { return g.slice(); });
        showFrame(v, s);
        begin(now);
      }
      var m = moves[i], k = Math.min(1, (now - t0) / dur);
      drawPac(v, lerp(from.pac[0], m.p[0], k), lerp(from.pac[1], m.p[1], k), m.r.choice, Math.abs(Math.sin(k * Math.PI)));
      m.g.forEach(function (g, j) { place(v.ghosts[j], lerp(from.ghosts[j][0], g[0], k), lerp(from.ghosts[j][1], g[1], k)); });
      if (k < 1) { frame = requestAnimationFrame(tick); return; }
      var d = v.dots[m.p[0] + "," + m.p[1]];
      if (d) d.style.display = "none";
      s.pac = m.p.slice();
      s.ghosts = m.g.map(function (g) { return g.slice(); });
      i++;
      if (m.c) {
        s.lives--;
        if (!s.lives || i >= moves.length) return over();
        status("Caught · " + s.lives + (s.lives === 1 ? " life" : " lives") + " left");
        pause = now + 1200;
        frame = requestAnimationFrame(tick);
        return;
      }
      if (i >= moves.length) return over(s.lives && !Object.keys(v.dots).some(function (key) { return v.dots[key].style.display !== "none"; }) ? "Cleared" : "Game over");
      begin(now);
      frame = requestAnimationFrame(tick);
    }
    showFrame(v, s);
    frame = requestAnimationFrame(function (now) { begin(now); tick(now); });
  }

  function load(game) {
    cancelAnimationFrame(frame);
    run++;
    view = build(game);
    var lat = game.moves.map(function (m) { return m.ms; }).filter(Boolean);
    note.textContent = game.model + (lat.length ? " · avg " + Math.round(lat.reduce(function (a, b) { return a + b; }, 0) / lat.length) + " ms per decision" : "") +
      " · " + game.moves.length + " moves, replayed at recorded speed.";
    var s0 = resetBoard(view);
    showFrame(view, s0);
    if (game.moves.length) panel(game.moves[0]);
    status(game.moves.length ? "Move 1 of " + game.moves.length : "No moves");
    if (io) io.disconnect();
    if (!("IntersectionObserver" in window)) { inView = true; return play(); }
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var was = inView; inView = e.isIntersecting;
        if (inView && !was && resume) { var r = resume; resume = null; requestAnimationFrame(r); }
      });
    }, { threshold: .4 });
    io.observe(fig);
    var first = new IntersectionObserver(function (entries) {  // autoplay once nearly all of the board is visible
      if (entries.some(function (e) { return e.isIntersecting; })) { first.disconnect(); play(); }
    }, { threshold: .4 });
    first.observe(fig);
  }

  fig.querySelector("[data-replay]").addEventListener("click", function () { if (view) play(); });
  fig.querySelector("[data-file]").addEventListener("change", function (e) {
    var f = e.target.files[0];
    if (f) f.text().then(function (t) { load(JSON.parse(t)); showChips(null); });
  });
  // ---- run picker (web/runs.json lists the bundled runs) -------------------------
  var runBar = fig.querySelector("[data-run-bar]"), runSel = fig.querySelector("[data-run]"), chips = fig.querySelector("[data-chips]");
  function chip(html) { return '<span class="chip">' + html + "</span>"; }
  function showChips(r) {
    chips.innerHTML = !r ? "" : ['<span class="chip strong">' + r.group.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</span>", chip("<b>" + r.score + "</b> pts"), chip(r.won ? "<b>cleared</b> the maze" : "<b>" + r.dotsLeft + "</b> dots left"),
      chip("<b>" + r.steps + "</b> moves"), r.avgMs ? chip("avg <b>" + r.avgMs + "</b> ms per decision") : ""].join("");
  }
  function buildPicker(runs) {
    var groups = {};
    runs.forEach(function (r) {
      var g = groups[r.group];
      if (!g) { g = groups[r.group] = document.createElement("optgroup"); g.label = r.group; runSel.appendChild(g); }
      var o = document.createElement("option");
      o.value = r.file; o.textContent = "Seed " + r.seed + " · " + r.score + " pts";
      g.appendChild(o);
    });
    runSel.addEventListener("change", function () {
      var r = runs.filter(function (x) { return x.file === runSel.value; })[0];
      loadFile(r.file, r).catch(function (err) { fail(r.file, err); });
    });
    runBar.hidden = false;
  }

  var srcParam = new URLSearchParams(location.search).get("src");
  var embedded = document.getElementById("sample-log");  // single-file build: a sample run is embedded
  function fromEmbedded() { try { load(JSON.parse(embedded.textContent)); return true; } catch (e) { return false; } }
  function loadFile(src, run) {
    return fetch(src).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (g) { load(g); showChips(run); });
  }
  function fail(src, err) {
    status("Could not load " + src + " (" + err.message + ") — pick a run file below."); fig.classList.remove("busy");
  }
  if (embedded && !srcParam && fromEmbedded()) { /* shown */ }
  else if (srcParam) loadFile(srcParam).catch(function (err) { fail(srcParam, err); });
  else fetch("runs.json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (runs) {
      buildPicker(runs);
      var first = runs.filter(function (r) { return r.file === "nimble_f5_s1.json"; })[0] || runs[0];
      runSel.value = first.file;
      return loadFile(first.file, first);
    })
    .catch(function () {  // no manifest (e.g. the page was opened from disk): fall back to the bundled sample
      loadFile("game.json").catch(function (err) { if (!(embedded && fromEmbedded())) fail("game.json", err); });
    });
})();
