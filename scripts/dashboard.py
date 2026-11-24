"""Render a profile dashboard using the repository-scoped GitHub Actions token."""
import json
import os
from collections import Counter
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel weekday } } }
    }
    repositories(first: 100, after: $after, privacy: PUBLIC, isFork: false, ownerAffiliations: OWNER) {
      pageInfo { hasNextPage endCursor }
      nodes { languages(first: 100, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
    }
  }
}
"""
owner = os.environ["GITHUB_REPOSITORY_OWNER"]
sizes = Counter()
colors = {}
cursor = None
while True:
    payload = {"query": QUERY, "variables": {"login": owner, "after": cursor}}
    req = Request("https://api.github.com/graphql", data=json.dumps(payload).encode(),
                  headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                           "Content-Type": "application/json"})
    with urlopen(req, timeout=40) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    user = result["data"]["user"]
    repos = user["repositories"]
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] += edge["size"]
            colors[name] = edge["node"]["color"] or "#9ca8a1"
    if not repos["pageInfo"]["hasNextPage"]:
        break
    cursor = repos["pageInfo"]["endCursor"]

collection = user["contributionsCollection"]
calendar = collection["contributionCalendar"]
weeks = calendar["weeks"]
days = [day for week in weeks for day in week["contributionDays"]]
svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 405" role="img" aria-labelledby="title desc">',
       '<title id="title">GitHub activity and contribution skyline</title>',
       '<desc id="desc">Each tile represents one day. Taller green columns indicate higher contribution levels. Weeks run from left to right.</desc>',
       '<rect width="800" height="405" rx="14" fill="#0d1513"/>',
       '<g font-family="ui-monospace,monospace">']

def label(x, y, content, size=15, color="#afc2b6"):
    svg.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(str(content))}</text>')

label(25, 31, "CONTRIBUTION SKYLINE", 18, "#e7f4ea")
label(25, 57, days[0]["date"] + "  /  " + days[-1]["date"])
levels = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
greens = ["#23352d", "#0e7338", "#28a34f", "#52cd68", "#93ec86"]

def face(points, fill):
    svg.append('<polygon points="' + ' '.join(f'{x:.2f},{y:.2f}' for x,y in points) + f'" fill="{fill}"/>')

for w, week in enumerate(weeks):
    for day in sorted(week["contributionDays"], key=lambda d: d["weekday"]):
        d = day["weekday"]
        x, y = 32 + 13*w + 8*d, 168 - 1.15*w + 6*d
        level = levels.index(day["contributionLevel"])
        h = [2, 10, 20, 32, 48][level]
        a,b,c,e = (x,y-h),(x+12,y-h-1),(x+19,y-h+4),(x+7,y-h+5)
        face([e,c,(c[0],c[1]+h),(e[0],e[1]+h)], "#21603b" if level else "#182820")
        face([b,c,(c[0],c[1]+h),(b[0],b[1]+h)], "#16422b" if level else "#15221b")
        face([a,b,c,e], greens[level])

for x, number, caption in [(25, calendar["totalContributions"], "Contributions"),
                           (290, collection["totalCommitContributions"], "Commit contributions"),
                           (575, sum(d["contributionCount"] > 0 for d in days), "Active days")]:
    label(x, 267, f"{number:,}", 29, "#e8f5ec")
    label(x, 291, caption)
svg.append('<path d="M25 312H775" stroke="#34463d"/>')
label(25, 340, "Top languages by code size", 17, "#e7f4ea")
label(25, 364, "Public repositories · forks excluded", 13)
for i, (name, size) in enumerate(sizes.most_common(4)):
    x = 25 + i*190
    svg.append(f'<circle cx="{x+4}" cy="386" r="4" fill="{colors[name]}"/>')
    label(x+15, 391, f"{name} {size/sizes.total():.0%}", 14)
svg.append('</g></svg>')
Path("assets/dashboard.svg").write_text("\n".join(svg) + "\n")
