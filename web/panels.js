/* Renders the /v1/systemone request and response as highlighted JSON. Shared by replay and live play. */
(function (root) {
  "use strict";
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }
  function span(cls, text) { return '<span class="' + cls + '">' + esc(text) + "</span>"; }

  // Pretty JSON; the option whose key equals `choice` inside questions.move.criteria is highlighted.
  function pretty(v, ind, path, choice) {
    var pad = new Array(ind + 1).join(" ");
    if (v === null) return span("n", "null");
    if (typeof v === "string") return span("s", '"' + v.replace(/"/g, '\\"') + '"');  // newlines stay real line breaks
    if (typeof v !== "object") return span("n", String(v));
    if (Array.isArray(v)) {
      if (v.every(function (x) { return x === null || typeof x !== "object"; })) return "[" + v.map(function (x) { return pretty(x, 0, "", choice); }).join(", ") + "]";
      return "[\n" + v.map(function (x) { return pad + "  " + pretty(x, ind + 2, path, choice); }).join(",\n") + "\n" + pad + "]";
    }
    return "{\n" + Object.keys(v).map(function (k) {
      var line = pad + "  " + span("k", '"' + k + '"') + ": " + pretty(v[k], ind + 2, path ? path + "." + k : k, choice);
      return path === "questions.move.criteria" && k === choice ? '<span class="hit">' + line + "</span>" : line;
    }).join(",\n") + "\n" + pad + "}";
  }
  function queryHTML(q, choice) { return pretty(q, 0, "", choice); }

  // r = {choice, probabilities?, confidence?}
  function answerHTML(r) {
    var probs = r.probabilities, keys = probs ? Object.keys(probs) : [];
    var L = [], q = function (s) { return span("k", '"' + s + '"'); };
    L.push("{", "  " + q("answers") + ": {", "    " + q("move") + ": {",
      "      " + q("type") + ": " + span("s", '"choice"') + ",",
      "      " + q("choice") + ": " + span("s", '"' + r.choice + '"') + (keys.length || r.confidence != null ? "," : ""));
    if (keys.length) {
      L.push("      " + q("probabilities") + ": {");
      keys.forEach(function (k, i) {
        L.push("        " + q(k) + ": " + span("n", probs[k].toFixed(2)) + (i < keys.length - 1 ? "," : ""));
      });
      L.push("      }" + (r.confidence != null ? "," : ""));
    }
    if (r.confidence != null) L.push("      " + q("confidence") + ": " + span("n", r.confidence.toFixed(2)));
    L.push("    }", "  }", "}");
    return L.join("\n");
  }
  function muted(text) { return span("muted", text); }

  root.PacPanels = { esc: esc, pretty: pretty, queryHTML: queryHTML, answerHTML: answerHTML, muted: muted };
})(this);
