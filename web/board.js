/* Shared SVG board drawing (maze, dots, ghosts, pacman) used by the replay and the play mode. */
(function (root) {
  "use strict";
  var NS = "http://www.w3.org/2000/svg", T = 16, R = 6.5;
  var WALL = "#E7E5E0", DOT = "#171717", PAC = "#DDAE4A", GHOSTS = ["#D9565C", "#DC7FB0", "#E08D55"];

  function el(parent, tag, attrs) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    parent.appendChild(n);
    return n;
  }
  // game = {maze: [string], start: {pac:[x,y], ghosts:[[x,y]..]}}; the start cell never shows a dot.
  function build(svg, game) {
    svg.textContent = "";
    var maze = game.maze, H = maze.length, W = maze[0].length;
    svg.setAttribute("viewBox", "0 0 " + W * T + " " + H * T);
    var walls = el(svg, "g", { fill: WALL, "shape-rendering": "crispEdges" }), dots = {};
    maze.forEach(function (row, y) {
      row.split("").forEach(function (c, x) {
        if (c === "#") el(walls, "rect", { x: x * T, y: y * T, width: T, height: T });
        if (c === "." && !(x === game.start.pac[0] && y === game.start.pac[1]))
          dots[x + "," + y] = el(svg, "circle", { cx: x * T + T / 2, cy: y * T + T / 2, r: 1.8, fill: DOT });
      });
    });
    var ghosts = game.start.ghosts.map(function (g, i) {
      var grp = el(svg, "g", {}), r = R;
      el(grp, "path", { d: "M" + -r + " 0A" + r + " " + r + " 0 0 1 " + r + " 0L" + r + " " + r + "L" + r * .66 + " " + r * .7 +
        "L" + r * .33 + " " + r + "L0 " + r * .7 + "L" + -r * .33 + " " + r + "L" + -r * .66 + " " + r * .7 + "L" + -r + " " + r + "Z",
        fill: GHOSTS[i % GHOSTS.length] });
      [-2.4, 2.4].forEach(function (dx) {
        el(grp, "circle", { cx: dx, cy: -1, r: 1.9, fill: "#fff" });
        el(grp, "circle", { cx: dx + .5, cy: -.8, r: .9, fill: DOT });
      });
      return grp;
    });
    var pac = el(svg, "path", { fill: PAC });
    return { game: game, dots: dots, ghosts: ghosts, pac: pac };
  }
  function place(g, x, y) { g.setAttribute("transform", "translate(" + (x * T + T / 2) + " " + (y * T + T / 2) + ")"); }
  function drawPac(v, x, y, dir, open) {
    var cx = x * T + T / 2, cy = y * T + T / 2;
    var face = { right: 0, down: Math.PI / 2, left: Math.PI, up: -Math.PI / 2 }[dir] || 0, a = .05 + .3 * open;
    v.pac.setAttribute("d", "M" + cx + " " + cy + "L" + (cx + R * Math.cos(face + a)) + " " + (cy + R * Math.sin(face + a)) +
      "A" + R + " " + R + " 0 1 1 " + (cx + R * Math.cos(face - a)) + " " + (cy + R * Math.sin(face - a)) + "Z");
  }
  function lerp(a, b, k) { return Math.abs(b - a) > 1 ? b : a + (b - a) * k; }  // jump across the tunnel / after a reset

  root.PacBoard = { build: build, place: place, drawPac: drawPac, lerp: lerp };
})(this);
