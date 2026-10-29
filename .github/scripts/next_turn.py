#!/usr/bin/env python3
"""Next Turn: tells the next player it's their turn.

Runs from .github/workflows/next-turn.yml after every merge to main, and
hourly. Each run:

  0. Does nothing unless PLAYERS.md says "Status: playing".
  1. Replays the merged "Turn N:" PRs against PLAYERS.md to work out who
     played last and which round it is.
  2. Makes sure exactly one open "your-turn" issue exists, assigned to the
     player after them (or opens "Game over" after the final round).
  3. If the assigned player has had the turn longer than the skip window,
     passes it to the player after them.

Every run is safe to repeat: if the right issue is already open, it does
nothing. Set DRY_RUN=1 to print what it would do without changing anything.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
NOW = datetime.now(timezone.utc)

TURN_LABEL = "your-turn"
OVER_LABEL = "game-over"
MARKER = re.compile(r"<!-- next-turn (.*?) -->")
LOGIN = re.compile(r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}")


def gh(*args, input=None):
    out = subprocess.run(["gh", *args], input=input, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def write(*args, input=None):
    if DRY_RUN:
        print("DRY RUN would call: gh", " ".join(args))
        return "{}"
    return gh(*args, input=input)


# --- The rules, from PLAYERS.md ---------------------------------------------

def read_status():
    m = re.search(r"^Status:\s*(\w+)", open("PLAYERS.md").read(), re.M)
    return m.group(1).lower() if m else "missing (add a 'Status: playing' line)"


def read_players():
    text = open("PLAYERS.md").read()
    players = re.findall(r"^\|\s*\d+\s*\|\s*@(\S+)\s*\|", text, re.M)
    bad = [p for p in players if not LOGIN.fullmatch(p)]
    if bad:
        sys.exit(f"PLAYERS.md still has placeholders or invalid usernames: "
                 f"{', '.join('@' + p for p in bad)}. Replace them with real GitHub usernames.")
    if not players:
        sys.exit("PLAYERS.md has no players.")
    dupes = sorted({p for p in players if [q.lower() for q in players].count(p.lower()) > 1})
    if dupes:
        sys.exit(f"PLAYERS.md lists {', '.join('@' + p for p in dupes)} more than once. "
                 f"List each player once.")
    rounds = re.search(r"^Rounds:\s*(\d+)\s*$", text, re.M)
    skip = re.search(r"^Skip after:\s*(\d+)\s*hours?\s*$", text, re.M)
    if not rounds or not skip:
        sys.exit("PLAYERS.md needs a 'Rounds: <number>' line and a 'Skip after: <number> hours' "
                 "line (hours only, e.g. 'Skip after: 72 hours' for three days).")
    return players, int(rounds.group(1)), timedelta(hours=int(skip.group(1)))


def read_pitch():
    """The "## Pitch" section of GAME.md, with HTML comments dropped and
    relative image links pointed at the repo so they render in an issue."""
    try:
        text = open("GAME.md").read()
    except FileNotFoundError:
        return ""
    m = re.search(r"^## Pitch\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    pitch = re.sub(r"<!--.*?-->", "", m.group(1) if m else "", flags=re.S)
    pitch = re.sub(r"(!\[[^\]]*\])\((?!https?:)(?:\.?/)?([^)\s]+)\)",
                   rf"\1(https://github.com/{REPO}/blob/main/\2?raw=true)", pitch)
    return re.sub(r"\n{3,}", "\n\n", pitch).strip()


# --- Where the game is ------------------------------------------------------

def last_turn_number():
    """The Turn: number in HANDOFF.md on main. The turn check validates it on
    every turn, so it's the source of truth (PR titles are free text)."""
    m = re.search(r"^\**Turn:\**\s*(\d+)", open("HANDOFF.md").read(), re.M)
    return int(m.group(1)) if m else 0


def game_state(players):
    """Replay merged turns. Returns (last turn number, last player index, round)."""
    owner, name = REPO.split("/")
    query = """query($owner: String!, $name: String!, $endCursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequests(states: MERGED, baseRefName: "main", first: 100, after: $endCursor) {
          nodes { mergedAt author { login }
                  commits(last: 1) { nodes { commit { messageHeadline } } } }
          pageInfo { hasNextPage endCursor }
        }
      }
    }"""
    # Every page, not just the latest 100: a big group's game (host PRs
    # included) passes 100, and dropping early turns miscounts the rounds.
    pages = json.loads(gh("api", "graphql", "--paginate", "--slurp", "-f", f"query={query}",
                          "-f", f"owner={owner}", "-f", f"name={name}"))
    prs = [pr for page in pages for pr in page["data"]["repository"]["pullRequests"]["nodes"]]
    # A turn PR is one whose commit subject is "Turn N: ...". The turn check
    # enforces that subject, so this doesn't depend on how the PR was titled.
    turns = sorted((pr["mergedAt"], pr["author"]["login"]) for pr in prs
                   if pr["commits"]["nodes"]
                   and re.match(r"Turn \d+:", pr["commits"]["nodes"][0]["commit"]["messageHeadline"]))

    lowered = [p.lower() for p in players]
    last_idx, rnd = None, 1
    for _, login in turns:
        if login.lower() not in lowered:
            continue  # someone no longer on the list; ignore for the rotation
        idx = lowered.index(login.lower())
        if last_idx is not None and idx <= last_idx:
            rnd += 1  # wrapped back to the top of the list
        last_idx = idx
    return last_turn_number(), last_idx, rnd


def after(players, idx, rnd):
    """The player after index idx, and the round they'd be playing in."""
    if idx is None:
        return 0, rnd
    nxt = (idx + 1) % len(players)
    return nxt, rnd + 1 if nxt <= idx else rnd


# --- Issues -----------------------------------------------------------------

def open_issues(label):
    return json.loads(gh("issue", "list", "--repo", REPO, "--label", label, "--state", "open",
                         "--json", "number,body,assignees"))


def marker(issue):
    m = MARKER.search(issue.get("body") or "")
    return dict(kv.split("=", 1) for kv in m.group(1).split()) if m else {}


def ensure_labels():
    have = {label["name"] for label in json.loads(gh("label", "list", "--repo", REPO, "--limit", "200",
                                                      "--json", "name"))}
    for name, color, desc in [(TURN_LABEL, "f9a03f", "Whose turn it is"),
                              (OVER_LABEL, "000000", "The game is finished")]:
        if name not in have:
            write("label", "create", name, "--repo", REPO, "--color", color, "--description", desc)


def turn_body(players, idx, turn, rnd, rounds, skip, assigned, after_login):
    login = players[idx]
    nxt, nxt_round = after(players, idx, rnd)
    final = nxt_round > rounds
    to = "nobody: this is the last turn of the game!" if final else f"@{players[nxt]}"
    skip_line = (f"you have {int(skip.total_seconds() // 3600)} hours from when this was assigned "
                 f"to you. After that, " + ("the game ends without this turn." if final
                                           else f"the turn passes to @{players[nxt]}."))
    pitch = read_pitch()
    pitch = f"\n\n**What we're building:** {pitch}" if pitch else ""
    return f"""@{login}, it's your turn! 🏃

**Round {rnd} of {rounds} · Turn {turn}**

**What this is:** commit relay. We're building one project together, one
commit per turn. Each player picks up where the last one left off and passes
the baton on.{pitch}

### Take your turn

You don't need to read the code. Open the repo in your AI coding agent
(Claude Code, Cursor, Codex…) and say:

> **Take a turn in commit relay.**

Your agent reads the last player's hand-off note and shows you where the game is.
Tell it, in plain English, what you'd like to add. Look over what it changed,
then merge the pull request it opens.

No copy of the repo yet? Your agent can clone it: `https://github.com/{REPO}`

<details>
<summary>Doing it by hand instead</summary>

1. `git fetch origin && git switch -c turn-{turn} origin/main`
2. Read `HANDOFF.md` and `git show HEAD` to see where the last player left off.
3. Make one change in `project/` and rewrite `HANDOFF.md` with `Turn: {turn}` and `To: {to}`.
4. Commit once as `Turn {turn}: …`, open a PR, and rebase-merge it once the check is green.

</details>

**Time:** {skip_line} This issue closes on its own when your turn merges.

<!-- next-turn turn={turn} round={rnd} player={login} assigned={assigned} after={after_login} -->
"""


def assign(number, login):
    """Assign the issue. Returns True if GitHub accepted the assignee.

    GitHub silently drops assignees who can't be assigned yet (for example,
    someone who hasn't accepted their collaborator invite)."""
    if DRY_RUN:
        print(f"DRY RUN would assign #{number} to @{login}")
        return True
    res = json.loads(gh("api", "-X", "POST", f"repos/{REPO}/issues/{number}/assignees",
                        "-f", f"assignees[]={login}"))
    return any(a["login"].lower() == login.lower() for a in res.get("assignees", []))


def open_turn(players, idx, turn, rnd, rounds, skip, after_login):
    login = players[idx]
    title = f"Round {rnd} · Turn {turn} is yours, @{login}"
    body = turn_body(players, idx, turn, rnd, rounds, skip, "pending", after_login)
    res = json.loads(write("api", "-X", "POST", f"repos/{REPO}/issues", "--input", "-",
                           input=json.dumps({"title": title, "body": body, "labels": [TURN_LABEL]})))
    number = res.get("number", 0)
    print(f"Opened #{number}: {title}")
    if assign(number, login):
        set_body(number, turn_body(players, idx, turn, rnd, rounds, skip, NOW.isoformat(), after_login))
    else:
        print(f"@{login} can't be assigned yet (invite not accepted?). Will retry hourly.")


def set_body(number, body, title=None):
    payload = {"body": body} | ({"title": title} if title else {})
    write("api", "-X", "PATCH", f"repos/{REPO}/issues/{number}", "--input", "-",
          input=json.dumps(payload))


def hold_clock():
    """While paused, keep moving the open turn's start time up to now, so the
    player gets their whole skip window back when the game resumes."""
    print("PLAYERS.md says Status: paused. No turns move; the current player's clock is held.")
    for issue in open_issues(TURN_LABEL):
        if marker(issue).get("assigned", "pending") != "pending":
            set_body(issue["number"], re.sub(r"(<!-- next-turn .*?assigned=)\S+",
                                             rf"\g<1>{NOW.isoformat()}", issue["body"]))


def close(number, comment):
    write("issue", "close", str(number), "--repo", REPO, "--comment", comment)


def game_over(players, rounds, last_turn):
    if open_issues(OVER_LABEL) or closed_over_exists():
        return
    everyone = " ".join(f"@{p}" for p in players)
    body = f"""🏁 **Game over.** {rounds} rounds, {last_turn} turns.

Thanks for playing, {everyone}.

Read the whole adventure back, start to finish:

```bash
git log --reverse --oneline
```
"""
    write("api", "-X", "POST", f"repos/{REPO}/issues", "--input", "-",
          input=json.dumps({"title": "Game over", "body": body, "labels": [OVER_LABEL]}))
    print("Opened the Game over issue.")


def closed_over_exists():
    return bool(json.loads(gh("issue", "list", "--repo", REPO, "--label", OVER_LABEL,
                              "--state", "closed", "--json", "number")))


# --- Main -------------------------------------------------------------------

def main():
    if not REPO:
        sys.exit("Set GITHUB_REPOSITORY to owner/repo.")
    status = read_status()
    if status == "paused":
        hold_clock()
        return
    if status != "playing":
        print(f"PLAYERS.md says Status: {status}. Set it to 'playing' to hand out turns.")
        return
    players, rounds, skip = read_players()
    ensure_labels()
    # Once "Game over" exists, the game stays over. Without this, a skip on
    # the last turn would reopen that turn an hour later, forever.
    if open_issues(OVER_LABEL) or closed_over_exists():
        print("The game is over. Delete the 'Game over' issue to play on.")
        return
    last_turn, last_idx, rnd = game_state(players)
    want_idx, want_round = after(players, last_idx, rnd)
    want_turn = last_turn + 1
    print(f"Last turn: {last_turn}. Next: turn {want_turn}, round {want_round}, "
          f"@{players[want_idx]}.")

    # Who played last. An issue opened after someone else (say, the run on a
    # merge saw the turn number before GitHub marked the PR merged) is
    # replaced. Skips keep it; older issues without after= are trusted.
    after_login = players[last_idx] if last_idx is not None else "-"
    issues = open_issues(TURN_LABEL)
    current = next((i for i in issues if marker(i).get("turn") == str(want_turn)
                    and marker(i).get("after", after_login).lower() == after_login.lower()), None)

    # A turn merged since the last issue: close the old issue(s).
    for issue in issues:
        if issue is not current:
            played = int(marker(issue).get("turn", "0")) < want_turn
            close(issue["number"], f"Turn {marker(issue).get('turn', '?')} has been played. 👋" if played
                  else "Replaced by a corrected issue.")

    if want_round > rounds:
        game_over(players, rounds, last_turn)
        return

    if current is None:
        open_turn(players, want_idx, want_turn, want_round, rounds, skip, after_login)
        return

    # The right issue is open. Retry a pending assignment, or skip if time is up.
    m = marker(current)
    idx, cur_round = players.index(m["player"]), int(m["round"])
    if m["assigned"] == "pending":
        if assign(current["number"], m["player"]):
            set_body(current["number"],
                     turn_body(players, idx, want_turn, cur_round, rounds, skip, NOW.isoformat(),
                               after_login))
            print(f"Assigned #{current['number']} to @{m['player']}.")
        return

    if NOW - datetime.fromisoformat(m["assigned"]) < skip:
        print(f"#{current['number']} is with @{m['player']}; time remains.")
        return

    nxt, nxt_round = after(players, idx, cur_round)
    if nxt_round > rounds:
        close(current["number"], f"@{m['player']} was skipped after "
                                 f"{int(skip.total_seconds() // 3600)} hours, and that was the "
                                 f"last turn.")
        game_over(players, rounds, last_turn)
        return

    login = players[nxt]
    print(f"Skipping @{m['player']}; turn {want_turn} goes to @{login}.")
    write("api", "-X", "DELETE", f"repos/{REPO}/issues/{current['number']}/assignees",
          "-f", f"assignees[]={m['player']}")
    write("issue", "comment", str(current["number"]), "--repo", REPO, "--body",
          f"@{m['player']} was skipped after {int(skip.total_seconds() // 3600)} hours. "
          f"@{login}, you're up!")
    assigned = NOW.isoformat() if assign(current["number"], login) else "pending"
    set_body(current["number"],
             turn_body(players, nxt, want_turn, nxt_round, rounds, skip, assigned, after_login),
             title=f"Round {nxt_round} · Turn {want_turn} is yours, @{login}")


if __name__ == "__main__":
    main()
