#!/usr/bin/env python3
"""Render the language bar in the README.

Sums GitHub's per-repo language byte counts across every repo I own, private
ones included, and writes dist/langs-{dark,light}.svg. Needs a token that can
see private repos in GH_TOKEN.
"""
import json
import os
import re
import urllib.request
from html import escape
from pathlib import Path

# repos whose bytes are generated or vendored code rather than mine
EXCLUDE = {"KarmaSDK", "Karma-GUI", "GigaLearnCPP", "GigaLearnCPP-ORIGINAL"}
TOP = 5
W, H = 880, 60
ICON = 18
# devicon logos in scripts/icons (MIT); anything not listed gets a colored dot
ICONS = {
    "C++": "cplusplus", "Rust": "rust", "Python": "python", "C": "c", "QML": "qt",
    "Shell": "bash", "TypeScript": "typescript", "JavaScript": "javascript", "C#": "csharp",
    "Lua": "lua", "Java": "java", "CSS": "css3", "CMake": "cmake",
}
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Roboto, 'Helvetica Neue', Arial, sans-serif"
THEMES = {
    "dark": dict(text="#e6edf3", muted="#8b949e", other="#8b949e", track="#21262d"),
    "light": dict(text="#1f2328", muted="#656d76", other="#8b949e", track="#eaeef2"),
}

QUERY = """
query($after: String) {
  viewer {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        languages(first: 30, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""


def fetch(token):
    sizes, colors, after = {}, {}, None
    while True:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": QUERY, "variables": {"after": after}}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "langs"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.load(r)
        if body.get("errors"):
            raise SystemExit(body["errors"])
        repos = body["data"]["viewer"]["repositories"]
        for repo in repos["nodes"]:
            if repo["name"] in EXCLUDE:
                continue
            for e in repo["languages"]["edges"]:
                name = e["node"]["name"]
                sizes[name] = sizes.get(name, 0) + e["size"]
                colors[name] = e["node"]["color"] or "#8b949e"
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    total = sum(sizes.values())
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])
    top = [(n, colors[n], 100 * s / total) for n, s in ranked[:TOP]]
    rest = sum(s for _, s in ranked[TOP:])
    if rest:
        top.append(("Other", None, 100 * rest / total))
    return top


def icon(name, x, y, fallback):
    """Inline a devicon logo as a nested <svg>; single-colour logos take the theme text colour."""
    path = Path(__file__).with_name("icons") / f"{ICONS.get(name, '')}.svg"
    if name not in ICONS or not path.exists():
        return f'<circle cx="{x + ICON / 2}" cy="{y + ICON / 2}" r="5.5" fill="{fallback}"/>'
    src = path.read_text()
    viewbox = re.search(r'viewBox="([^"]+)"', src).group(1)
    inner = re.sub(r"^.*?<svg[^>]*>", "", src, count=1, flags=re.S).rsplit("</svg>", 1)[0]
    fill = "" if 'fill="' in inner else f' fill="{fallback}"'
    return f'<svg x="{x}" y="{y}" width="{ICON}" height="{ICON}" viewBox="{viewbox}"{fill}>{inner}</svg>'


def render(t, langs):
    out = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Languages">\n'
        f"  <style>text {{ font-family: {SANS}; }}</style>\n"
        f"  <defs>\n"
        f'    <clipPath id="bar"><rect width="{W}" height="10" rx="5"/></clipPath>\n'
        f'    <clipPath id="reveal"><rect width="0" height="10">'
        f'<animate attributeName="width" from="0" to="{W}" begin="0.1s" dur="0.9s" fill="freeze" calcMode="spline" keySplines="0.25 0.1 0.25 1"/>'
        f"</rect></clipPath>\n"
        f"  </defs>\n"
        f'  <rect width="{W}" height="10" rx="5" fill="{t["track"]}"/>\n'
        f'  <g clip-path="url(#reveal)"><g clip-path="url(#bar)">\n'
    )
    x = 0.0
    for name, color, pct in langs:
        w = W * pct / 100
        out += f'    <rect x="{x:.2f}" width="{w:.2f}" height="10" fill="{color or t["other"]}"/>\n'
        x += w
    out += "  </g></g>\n"
    slot = W // len(langs)
    for i, (name, color, pct) in enumerate(langs):
        x = i * slot
        out += (
            f'  {icon(name, x, 29, t["text"] if color else t["other"])}\n'
            f'  <text x="{x + ICON + 8}" y="43" font-size="13" fill="{t["text"]}"><tspan font-weight="600">{escape(name)}</tspan>'
            f'<tspan fill="{t["muted"]}" dx="6">{pct:.1f}%</tspan></text>\n'
        )
    return out + "</svg>\n"


def main():
    token = os.environ.get("GH_TOKEN") or exit("GH_TOKEN is not set")
    langs = fetch(token)
    out = Path("dist")
    out.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        (out / f"langs-{theme}.svg").write_text(render(t, langs))
    print(", ".join(f"{n} {p:.1f}%" for n, _, p in langs))


if __name__ == "__main__":
    main()
