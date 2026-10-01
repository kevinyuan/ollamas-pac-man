/* "Model plays": the game runs here in the browser; every move is decided by an AI endpoint you provide
 * (Ollama's /v1/systemone). Nothing is sent anywhere else. Needs panels.js, board.js, game.js, prompts.js. */
(function () {
  "use strict";
  var fig = document.querySelector("[data-live]");
  if (!fig) return;
  var $ = function (n) { return fig.querySelector("[data-" + n + "]"); };
  var svg = $("live-maze"), statusEl = $("live-status"), queryEl = $("live-query"), answerEl = $("live-answer");
  var urlIn = $("endpoint"), modelIn = $("model"), fmtSel = $("format"), fmtNote = $("format-note"), testOut = $("test-result");
  var startBtn = $("live-start"), stepBtn = $("live-step");
  var DEFAULTS = { endpoint: "http://localhost:11434", model: "nimble", format: "rays-side" };
  var MOVE_MS = 200, CAUGHT_PAUSE = 900, TIMEOUT = 120000;
  var game, view, token = 0, running = false, busy = false, ctrl = null, lat = [], decisions = 0;
  var key = function (p) { return p[0] + "," + p[1]; };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  function setStatus(t, state) { statusEl.textContent = t; statusEl.setAttribute("data-state", state || ""); }
  var snap = function () { return { pac: game.pac.slice(), ghosts: game.ghosts.map(function (g) { return g.slice(); }) }; };

  // ---- settings (kept in localStorage; URL parameters win: ?endpoint=&model=&format=&autostart=1) ----
  Object.keys(PacPrompts.FORMATS).forEach(function (id) {
    var o = document.createElement("option"); o.value = id; o.textContent = PacPrompts.FORMATS[id].name; fmtSel.appendChild(o);
  });
  var saved = {}, params = new URLSearchParams(location.search);
  try { saved = JSON.parse(localStorage.getItem("pacman.live") || "{}"); } catch (e) {}
  urlIn.value = params.get("endpoint") || saved.endpoint || DEFAULTS.endpoint;
  modelIn.value = params.get("model") || saved.model || DEFAULTS.model;
  fmtSel.value = PacPrompts.FORMATS[params.get("format") || saved.format] ? (params.get("format") || saved.format) : DEFAULTS.format;
  function persist() {
    fmtNote.textContent = PacPrompts.FORMATS[fmtSel.value].note;
    try { localStorage.setItem("pacman.live", JSON.stringify({ endpoint: urlIn.value, model: modelIn.value, format: fmtSel.value })); } catch (e) {}
  }
  [urlIn, modelIn, fmtSel].forEach(function (el) { el.addEventListener("change", persist); });
  persist();
  var base = function () { return (urlIn.value || DEFAULTS.endpoint).trim().replace(/\/+$/, "").replace(/\/v1\/systemone$/, ""); };
  var modelName = function () { return modelIn.value.trim() || DEFAULTS.model; };

  // ---- talking to the endpoint ----------------------------------------------
  function http(path, body, signal) {
    return fetch(base() + path, body === undefined ? { signal: signal } : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: signal
    }).then(function (r) {
      if (r.ok) return r.json();
      return r.text().then(function (t) { var e = new Error("HTTP " + r.status); e.status = r.status; e.body = t.slice(0, 300); throw e; });
    });
  }
  var HELP = "Ollama only accepts pages from http://localhost by default. If this page is a file you opened from disk, or is hosted " +
    "somewhere else, start Ollama with OLLAMA_ORIGINS set, e.g.  OLLAMA_ORIGINS=\"*\" ollama serve  (macOS app: " +
    "launchctl setenv OLLAMA_ORIGINS \"*\" and restart it; Linux service: add Environment=\"OLLAMA_ORIGINS=*\" and restart).";
  function explain(e) {
    if (e.status === 403) return "403 Forbidden: the endpoint rejected this page's origin. " + HELP;
    if (e.status === 404) return "404 from " + base() + (e.body ? " (" + e.body.replace(/\s+/g, " ") + ")" : "") +
      ". Needs Ollama 0.35 or newer with a decision model pulled (ollama pull " + modelName() + ").";
    if (e.status) return e.message + (e.body ? ": " + e.body.replace(/\s+/g, " ") : "");
    if (e.name === "AbortError") return "Timed out after " + TIMEOUT / 1000 + " s.";
    return "Cannot reach " + base() + " (the server is down, the URL is wrong, or the browser blocked it with CORS / mixed content). " + HELP;
  }
  function withTimeout() {
    ctrl = new AbortController();
    var t = setTimeout(function () { ctrl.abort(); }, TIMEOUT);
    return { signal: ctrl.signal, done: function () { clearTimeout(t); } };
  }

  $("test").addEventListener("click", function () {
    var t0 = performance.now(), c = withTimeout();
    testOut.className = "test-result"; testOut.textContent = "Testing…";
    var probe = new Game0().g;
    http("/api/version", undefined, c.signal).catch(function () { return {}; }).then(function (v) {
      return http("/v1/systemone", PacPrompts.build(fmtSel.value, probe, modelName()), c.signal).then(function (res) {
        var a = res.answers.move;
        testOut.className = "test-result ok";
        testOut.textContent = "Connected" + (v.version ? " to Ollama " + v.version : "") + " · " + modelName() + " answered “" + a.choice +
          "” in " + Math.round(performance.now() - t0) + " ms.";
      });
    }).catch(function (e) { testOut.className = "test-result err"; testOut.textContent = explain(e); }).then(c.done);
  });
  function Game0() { this.g = new PacGame.Game(); }

  // ---- the game ---------------------------------------------------------------
  function stats() {
    $("live-score").textContent = game.score;
    $("live-lives").textContent = new Array(Math.max(0, game.lives) + 1).join("♥ ").trim() || "–";
    $("live-dots").textContent = game.dotsLeft();
    $("live-decisions").textContent = decisions;
    $("live-latency").textContent = lat.length ? Math.round(lat.reduce(function (a, b) { return a + b; }, 0) / lat.length) + " ms" : "–";
  }
  function buttons() {
    startBtn.textContent = running ? "Pause" : (game.steps ? "Resume" : "Start");
    startBtn.classList.toggle("primary", !running);
    startBtn.disabled = game.over;
    stepBtn.disabled = running || busy || game.over;
  }
  function show(s, dir) {
    PacBoard.drawPac(view, s.pac[0], s.pac[1], dir || "left", .8);
    s.ghosts.forEach(function (g, j) { PacBoard.place(view.ghosts[j], g[0], g[1]); });
  }
  function newGame() {
    token++; if (ctrl) ctrl.abort();
    running = busy = false; lat = []; decisions = 0;
    game = new PacGame.Game();
    view = PacBoard.build(svg, { maze: game.maze, start: { pac: PacGame.PAC_START, ghosts: PacGame.GHOST_STARTS } });
    show(snap());
    queryEl.innerHTML = PacPanels.muted("The request for each move appears here.");
    answerEl.innerHTML = PacPanels.muted("The model's answer appears here.");
    setStatus("Press Start. Each move is decided by " + modelName() + ".");
    stats(); buttons();
  }

  function animate(from, to, dir, my) {
    return new Promise(function (resolve) {
      var t0 = performance.now();
      (function frame(now) {
        if (my !== token) return resolve();
        var k = Math.min(1, ((now || performance.now()) - t0) / MOVE_MS);
        PacBoard.drawPac(view, PacBoard.lerp(from.pac[0], to.pac[0], k), PacBoard.lerp(from.pac[1], to.pac[1], k), dir, Math.abs(Math.sin(k * Math.PI)));
        to.ghosts.forEach(function (g, j) { PacBoard.place(view.ghosts[j], PacBoard.lerp(from.ghosts[j][0], g[0], k), PacBoard.lerp(from.ghosts[j][1], g[1], k)); });
        if (k < 1) requestAnimationFrame(frame); else resolve();
      })();
    });
  }
  function applyMove(action, my) {
    var prev = snap(), caught = game.step(action);
    var at = caught ? game.collision.pac : game.pac, d = view.dots[key(at)];
    if (d && !game.dots[key(at)]) d.style.display = "none";
    var to = caught ? { pac: game.collision.pac, ghosts: game.collision.ghosts } : snap();
    return animate(prev, to, action, my).then(function () {
      stats();
      if (!caught || my !== token) return;
      if (game.over) return;
      setStatus("Caught! " + game.lives + (game.lives === 1 ? " life" : " lives") + " left");
      return sleep(CAUGHT_PAUSE).then(function () { if (my === token) show(snap()); });
    });
  }

  // One decision and one move. Resolves to false when the run should stop (error, restart).
  async function turn() {
    var my = token, req = PacPrompts.build(fmtSel.value, game, modelName());
    var shown = { state: req.state, questions: req.questions };
    queryEl.innerHTML = PacPanels.queryHTML(shown, null);
    answerEl.innerHTML = PacPanels.muted("Waiting for the model…");
    setStatus("Thinking… (move " + (game.steps + 1) + ")", "thinking");
    var c = withTimeout(), t0 = performance.now(), res;
    try { res = await http("/v1/systemone", req, c.signal); }
    catch (e) {
      c.done();
      if (my !== token) return false;
      answerEl.innerHTML = '<span class="err">' + PacPanels.esc(explain(e)) + "</span>";
      setStatus("Stopped: the endpoint did not answer. Press Resume to retry.", "error");
      return false;
    }
    c.done();
    if (my !== token) return false;
    var ms = Math.round(performance.now() - t0), a = res && res.answers && res.answers.move;
    if (!a || !a.choice) {
      answerEl.innerHTML = '<span class="err">Unexpected response (no answers.move.choice).</span>';
      setStatus("Stopped: unexpected response.", "error");
      return false;
    }
    var legal = game.legalActions(), choice = a.choice, note = "";
    if (legal.indexOf(choice) < 0) {  // same fallback as the Python agent: best legal option by probability
      var p = a.probabilities || {};
      choice = legal.slice().sort(function (x, y) { return (p[y] || 0) - (p[x] || 0); })[0];
      note = "\n(the model answered “" + a.choice + "”, which is not a legal move; playing " + choice + ")";
    }
    lat.push(ms); decisions++;
    queryEl.innerHTML = PacPanels.queryHTML(shown, choice);
    answerEl.innerHTML = PacPanels.answerHTML({ choice: choice, probabilities: a.probabilities, confidence: a.confidence }) +
      "\n" + PacPanels.muted("// " + ms + " ms" + note);
    setStatus("Move " + (game.steps + 1) + " · " + choice + " · " + ms + " ms");
    await applyMove(choice, my);
    return my === token;
  }
  function finish() {
    if (game.won) setStatus("Cleared the maze! Score " + game.score + ".", "done");
    else if (game.lives <= 0) setStatus("Game over. Score " + game.score + ".", "done");
  }
  async function loop() {
    if (busy) return;
    running = true; buttons();
    while (running && !game.over) {
      busy = true;
      var ok = await turn();
      busy = false;
      if (!ok) break;
    }
    var stopped = !game.over && running;  // paused by the user (running is cleared then) vs ended
    running = false; busy = false; buttons();
    if (game.over) finish();
  }
  function stepOnce() {
    if (busy || running || game.over) return;
    busy = true; buttons();
    turn().then(function () { busy = false; buttons(); if (game.over) finish(); });
  }
  startBtn.addEventListener("click", function () {
    if (running) { running = false; setStatus("Pausing after this move…"); buttons(); } else loop();
  });
  stepBtn.addEventListener("click", stepOnce);
  $("live-restart").addEventListener("click", newGame);
  window.addEventListener("pactab", function (e) { if (e.detail !== "live") running = false; });

  newGame();
  if (params.get("autostart") === "1" && location.hash === "#live") loop();
})();
