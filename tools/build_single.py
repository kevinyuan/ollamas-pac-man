"""Bundle web/ into one self-contained HTML file (no server needed):  python3 tools/build_single.py [out.html]

Inlines the stylesheet and every script and embeds a sample run (with requests) for the replay tab.
Open the file directly, or serve it from anywhere; the live tab only needs an AI endpoint URL.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SAMPLE = WEB / "nimble_f5_s1.json"


def main(out):
    html = (WEB / "index.html").read_text()
    html = re.sub(r'<link rel="stylesheet" href="([^"]+)">',
                  lambda m: "<style>\n" + (WEB / m.group(1)).read_text() + "\n</style>", html)

    def script(m):
        src = m.group(1)
        body = (WEB / src).read_text()
        assert "</script" not in body, f"{src} contains </script"
        extra = ""
        if src == "replay.js":  # the sample run must exist before the replay script reads it
            data = SAMPLE.read_text().replace("</", "<\\/")
            extra = '<script type="application/json" id="sample-log">' + data + "</script>\n"
        return extra + "<script>\n" + body + "\n</script>"
    html = re.sub(r'<script src="([^"]+)"></script>', script, html)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
    print(f"{out}: {len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "dist" / "pacman.html"))
