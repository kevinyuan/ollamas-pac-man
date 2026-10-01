"""Turn docs/substack-post.md into docs/substack-post.html, a page for copying the post into Substack's editor.

  python3 tools/post_to_html.py [in.md] [out.html]      (needs pandoc)

The first line (# Title) and the italic line after it become the title and subtitle fields; the rest is the body.
The page has one copy button for each, and the body is copied as rich text so headings, links, lists and code
blocks survive pasting.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "substack-post.md"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "substack-post.html"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ (copy into Substack)</title>
<style>
:root{--line:#E7E5E0;--ink:#171717;--muted:#737373}
*{box-sizing:border-box}
body{margin:0;background:#FAFAF9;color:var(--ink);font:17px/1.7 Georgia,"Times New Roman",serif}
.bar{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid var(--line);padding:10px 16px;font:14px/20px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.bar .row{max-width:1000px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bar b{margin-right:4px}
button{height:32px;padding:0 14px;border:1px solid var(--line);border-radius:9999px;background:#fff;color:var(--ink);font:500 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;cursor:pointer}
button:hover{background:#F4F3F0}button.ok{background:#0b7a4b;border-color:#0b7a4b;color:#fff}
.msg{color:var(--muted);font-size:13px}
main{max-width:720px;margin:28px auto 80px;padding:0 16px}
.field{margin:0 0 28px;padding:14px 16px;border:1px dashed var(--line);border-radius:12px;background:#fff}
.field small{display:block;margin-bottom:4px;color:var(--muted);font:12px/16px -apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase}
.field h1{margin:0;font-size:30px;line-height:1.25}
.field p{margin:0;color:#404040;font-style:italic}
article{background:#fff;padding:8px 28px 24px;border:1px solid var(--line);border-radius:12px}
article h2{margin:1.8em 0 .5em;font-size:24px;line-height:1.3}
article img{display:block;max-width:100%;height:auto;margin:1.2em auto;border:1px solid var(--line)}
article pre{overflow-x:auto;padding:12px 14px;background:#F4F3F0;border-radius:8px;font-size:14px;line-height:1.5}
article code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em}
article :not(pre)>code{background:#F4F3F0;padding:1px 5px;border-radius:4px}
article a{color:inherit}
</style>
</head>
<body>
<div class="bar"><div class="row">
  <b>Copy into Substack:</b>
  <button data-copy="title">1. Title</button>
  <button data-copy="subtitle">2. Subtitle</button>
  <button data-copy="body">3. Body</button>
  <span class="msg" id="msg">Paste the body into the editor, then upload the image if it does not load.</span>
</div></div>
<main>
  <div class="field" id="title"><small>Title</small><h1>__TITLE__</h1></div>
  <div class="field" id="subtitle"><small>Subtitle</small><p>__SUBTITLE__</p></div>
  <article id="body">
__BODY__
  </article>
</main>
<script>
(function () {
  var msg = document.getElementById("msg");
  function done(btn, text) { btn.classList.add("ok"); msg.textContent = text; setTimeout(function () { btn.classList.remove("ok"); }, 1500); }
  function selectNode(node) { var r = document.createRange(); r.selectNodeContents(node); var s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-copy"), node = document.getElementById(id);
      if (id !== "body") {  // plain text for the single-line fields
        var text = node.querySelector("h1,p").textContent.trim();
        (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { done(btn, "Copied the " + id + "."); },
          function () { selectNode(node.querySelector("h1,p")); document.execCommand("copy"); done(btn, "Copied the " + id + "."); });
        return;
      }
      var htmlText = node.innerHTML;  // rich text, so headings, links, lists and code blocks survive pasting
      if (navigator.clipboard && window.ClipboardItem) {
        navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([htmlText], { type: "text/html" }), "text/plain": new Blob([node.innerText], { type: "text/plain" }) })])
          .then(function () { done(btn, "Copied the body as rich text."); }, function () { selectNode(node); document.execCommand("copy"); done(btn, "Copied the body."); });
      } else { selectNode(node); document.execCommand("copy"); done(btn, "Copied the body."); }
    });
  });
})();
</script>
</body>
</html>
"""


def main():
    text = SRC.read_text()
    m = re.match(r"# (.+)\n\n\*(.+)\*\n\n", text)
    assert m, "expected '# Title', a blank line, '*subtitle*', a blank line at the top"
    title, subtitle, body_md = m.group(1), m.group(2), text[m.end():]
    body = subprocess.run(["pandoc", "-f", "gfm", "-t", "html5", "--no-highlight", "--wrap=none"],
                          input=body_md, capture_output=True, text=True, check=True).stdout
    page = (TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__SUBTITLE__", html.escape(subtitle))
            .replace("__BODY__", body))
    OUT.write_text(page)
    print(f"{OUT}  ({len(page) / 1024:.0f} KB)  h2: {body.count('<h2')}  code blocks: {body.count('<pre')}  "
          f"images: {body.count('<img')}  links: {body.count('<a ')}")


if __name__ == "__main__":
    main()
