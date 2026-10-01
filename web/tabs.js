/* Tab switching: Replay / You play / Model plays. Other scripts listen for the "pactab" event to pause. */
(function () {
  "use strict";
  var panels = { replay: document.querySelector("[data-pacman]"), play: document.querySelector("[data-play]"), live: document.querySelector("[data-live]") };
  var lede = document.querySelector("[data-lede]");
  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-tab]"));
  var LEDE = {
    replay: "A recorded game: at every move the agent answers one <code>choice</code> question through <code>/v1/systemone</code>, and the page replays that run.",
    play: "Your turn. Steer with the arrow keys or WASD (or swipe, or the buttons below). Pac-Man keeps moving; you and the ghosts move one cell per beat.",
    live: "Let a model drive. Point the page at your own Ollama endpoint, and every move is decided by a live <code>/v1/systemone</code> request that you can read on the right. Nothing leaves your browser except those requests."
  };
  function show(name) {
    if (!panels[name]) name = "replay";
    Object.keys(panels).forEach(function (k) { if (panels[k]) panels[k].hidden = k !== name; });
    tabs.forEach(function (t) { t.setAttribute("aria-selected", String(t.getAttribute("data-tab") === name)); });
    if (lede) lede.innerHTML = LEDE[name];
    try { history.replaceState(null, "", name === "replay" ? location.pathname + location.search : location.search + "#" + name); } catch (e) {}
    window.dispatchEvent(new CustomEvent("pactab", { detail: name }));
  }
  tabs.forEach(function (t) { t.addEventListener("click", function () { show(t.getAttribute("data-tab")); }); });
  show(location.hash.slice(1));
})();
