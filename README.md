# Commit Relay

A shared adventure, played with git. A group of people and their AI coding
agents build one project **one commit at a time**. Each turn is one leg of
the relay: pick up where the last player left off, add one commit, and pass
the baton on. Nobody owns the plan; the group finds out where it's going
together. `git log --oneline` is the story so far.

It works for friends, a team offsite, or a class. Players don't need to be
developers: their coding agent reads the rules in [`AGENTS.md`](AGENTS.md),
explains the game, and handles the git.

## How a turn works

1. When it's your turn, GitHub notifies you: an issue titled "Turn N is
   yours" gets assigned to you.
2. The last player left a hand-off note in [`HANDOFF.md`](HANDOFF.md): what
   they did, where they were steering, and a thread you could pick up.
3. You (or your agent) start from that note and the last turn's diff. The
   rest of the history is there if you want it.
4. You add **one commit** to [`project/`](project/) that takes the adventure
   a step further, and rewrite `HANDOFF.md` for the next player.
5. You open a PR. An Action checks that it's a valid turn, you rebase-merge
   it, and the next player gets their "your turn" issue.

What we're building, and how to look at it, is in [`GAME.md`](GAME.md).

---

## Start your own game

You're the **host**: you pick what gets built, invite the players, and keep
the rules. It takes about ten minutes.

### 1. Make the repo

Click **Use this template → Create a new repository** at the top of this
page. Public or private both work. Then, in your new repo's **Settings**:

- **General → Pull Requests:** allow only **Rebase merging**, so every turn
  lands as exactly one commit and `git log` reads as the transcript.
- **Collaborators:** add each player with **Write** access. They need it to
  push a branch and merge their own turn.
- **Branches** (optional): protect `main` and require the
  `Relay Turn Check` status to pass before merging.

### 2. Set up the game

Edit these files (on GitHub or locally) and commit them straight to `main`:

| File | What to do |
|---|---|
| [`GAME.md`](GAME.md) | Write the pitch: what you're building, plus the constraint that gives it a voice. Say how players can see it. |
| [`project/README.md`](project/README.md) | Set the house style: the rules every turn has to follow. |
| [`HANDOFF.md`](HANDOFF.md) | Write the opening hand-off for Turn 1, and set `From:` and `To:`. |
| [`PLAYERS.md`](PLAYERS.md) | Set `Host:`, list the players in turn order, and pick rounds and the skip window. |

If you want to set the scene yourself, also put a starting point in
`project/` (an opening screen, a first paragraph, a blank canvas). Otherwise
Turn 1 starts from nothing.

### 3. Start

In `PLAYERS.md`, change `Status: setup` to `Status: playing` and commit to
`main`. Within a minute the `Next Turn` Action opens "Round 1 · Turn 1 is
yours" and assigns it to the first player. From then on it runs itself:
each merged turn opens the next one, slow players get skipped, and after the
last round it opens a "Game over" issue.

Set `Status: paused` to stop handing out turns for a while.

### Ideas for a first game

What works best is a small canvas with tight constraints, so every turn
looks like it belongs:

- **A retro game:** an NES-style side-scroller, 256×240 pixels, NES palette
  only, no build step. (This is where commit relay started, as a game about a black coyote in San Diego.)
- **A story:** one chapter per turn, with a fixed narrator and setting.
- **A tiny website:** a single HTML page for a made-up business.
- **A song or poem:** in a text format like ABC notation, or in strict meter.
- **An API or CLI:** each turn adds one command or endpoint, with tests.

### If something goes wrong

- **No "your turn" issue appeared:** check the **Actions** tab. If `Next Turn`
  failed with a permissions error, go to **Settings → Actions → General →
  Workflow permissions**, choose **Read and write**, and run it again from the
  Actions tab (**Run workflow**).
- **A player can't be assigned:** they haven't accepted their collaborator
  invite yet. The Action retries every hour.
- **The game went quiet:** GitHub turns off hourly workflows in public repos
  after 60 days with no commits. Re-enable `Next Turn` in the Actions tab.

---

## Taking a turn

**Not a developer?** Open the repo in a coding agent (Claude Code, Cursor,
Codex) and say *"Take a turn in commit relay."* It shows you where the
game is and what the last player handed off, then asks what you'd like to
add. Ask it for more of the story so far any time. Tell it in plain English. Look over what it changed before you merge.

**To see the project** without an agent, click the green **Code** button →
**Download ZIP**, unzip it, and follow "How to see it" in `GAME.md`.

**Doing it by hand:**

```bash
git fetch origin && git switch -c turn-N origin/main
cat GAME.md HANDOFF.md && git show HEAD
# make one change in project/, rewrite HANDOFF.md
git commit -am "Turn N: what you did"
gh pr create --fill
```

## Rules at a glance

| Enforced by CI | Honor system |
|---|---|
| Exactly 1 commit per PR | Pick up the thread the last player left |
| Branch includes the latest `main` | Only play when the turn is assigned to you |
| `HANDOFF.md` rewritten, `Turn:` +1 | Build on the last turn; don't wipe it out |
| Subject starts with `Turn N:` | No secrets or personal data, ever |
| Players don't touch `.github/`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `PLAYERS.md`, `GAME.md` | |

## License

[MIT](LICENSE). The template is yours to copy and change. What your group
builds with it is yours too.
