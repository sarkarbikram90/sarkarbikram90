import os
import requests
import re
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "sarkarbikram90")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


# ── Fetch pinned repos via GraphQL ────────────────────────────────────────────

def get_pinned_repos():
    query = """
    {
      user(login: "%s") {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              description
              stargazerCount
              forkCount
              primaryLanguage { name color }
              url
              isPrivate
            }
          }
        }
      }
    }
    """ % USERNAME

    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query},
        headers=HEADERS,
    )
    data = response.json()
    return data["data"]["user"]["pinnedItems"]["nodes"]


# ── Fetch recent public activity ──────────────────────────────────────────────

def get_recent_activity():
    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=30"
    response = requests.get(url, headers=HEADERS)
    events = response.json()

    seen = set()
    activity_lines = []

    event_map = {
        "PushEvent":         ("📦", lambda e: f"Pushed to `{e['repo']['name'].split('/')[-1]}`"),
        "CreateEvent":       ("🌿", lambda e: f"Created `{e['payload'].get('ref') or e['repo']['name'].split('/')[-1]}`"),
        "WatchEvent":        ("⭐", lambda e: f"Starred `{e['repo']['name'].split('/')[-1]}`"),
        "ForkEvent":         ("🍴", lambda e: f"Forked `{e['repo']['name'].split('/')[-1]}`"),
        "IssuesEvent":       ("🐛", lambda e: f"{e['payload']['action'].capitalize()} issue in `{e['repo']['name'].split('/')[-1]}`"),
        "PullRequestEvent":  ("🔀", lambda e: f"{e['payload']['action'].capitalize()} PR in `{e['repo']['name'].split('/')[-1]}`"),
        "ReleaseEvent":      ("🚀", lambda e: f"Released `{e['payload']['release']['tag_name']}` in `{e['repo']['name'].split('/')[-1]}`"),
    }

    for event in events:
        etype = event.get("type")
        repo = event["repo"]["name"]
        key = f"{etype}-{repo}"

        if key in seen or etype not in event_map:
            continue

        seen.add(key)
        icon, label_fn = event_map[etype]
        label = label_fn(event)
        date = event["created_at"][:10]
        activity_lines.append(f"| {icon} | {label} | `{date}` |")

        if len(activity_lines) == 5:
            break

    return activity_lines


# ── Build markdown blocks ──────────────────────────────────────────────────────

def build_repos_block(repos):
    lines = ["```"]
    for repo in repos:
        lang = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "—"
        desc = repo["description"] or "no description"
        stars = repo["stargazerCount"]
        forks = repo["forkCount"]
        name = repo["name"]
        lines.append(f"📦 {name:<35} ★ {stars}  🍴 {forks}  [{lang}]")
        lines.append(f"   └─ {desc}")
    lines.append("```")
    return "\n".join(lines)


def build_activity_block(activity_lines):
    lines = [
        "| | Activity | Date |",
        "|---|---|---|",
    ]
    lines += activity_lines if activity_lines else ["| — | No recent activity | — |"]
    return "\n".join(lines)


# ── Inject into README between markers ────────────────────────────────────────

def inject_block(content, marker, block):
    pattern = rf"(<!-- {marker}_START -->).*?(<!-- {marker}_END -->)"
    replacement = rf"\1\n{block}\n\2"
    return re.sub(pattern, replacement, content, flags=re.DOTALL)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open("README.md", "r") as f:
        content = f.read()

    print("Fetching pinned repos...")
    repos = get_pinned_repos()
    repos_block = build_repos_block(repos)

    print("Fetching recent activity...")
    activity = get_recent_activity()
    activity_block = build_activity_block(activity)

    # Inject timestamp
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    timestamp_block = f"*Last updated: `{now}`*"

    content = inject_block(content, "REPOS", repos_block)
    content = inject_block(content, "ACTIVITY", activity_block)
    content = inject_block(content, "TIMESTAMP", timestamp_block)

    with open("README.md", "w") as f:
        f.write(content)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()