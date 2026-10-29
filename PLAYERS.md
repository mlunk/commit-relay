# Players

Turns go down this list, then wrap back to the top. One pass through the
list is a round. Only the host edits this file.

Status: setup
Host: @your_username
Rounds: 3
Skip after: 48 hours

| # | Player |
|---|---|
| 1 | @your_username |
| 2 | @player_two |
| 3 | @player_three |

## Settings

Replace every `@your_username`-style placeholder with a real GitHub username.
The underscores make them impossible usernames, so nobody real gets
mentioned, and the game won't start until they're all gone.

- **Status:** `setup` while you get ready, `playing` to start the game, and
  `paused` to stop handing out turns for a while. Nothing happens until it
  says `playing`.
- **Host:** who may change anything outside `project/` and `HANDOFF.md`
  (the rules, `GAME.md`, this file). The repo owner can too.
- **Rounds:** how many times the turn goes all the way down the list.
- **Skip after:** how long a player has to merge their turn before it passes
  to the next player.

## How it works

- **Your turn:** when a turn merges, the `Next Turn` Action opens an issue
  titled "Round R · Turn N is yours" and assigns it to the next player.
  GitHub notifies you. The issue closes on its own when your turn merges.
- **Who's next:** always the player listed after whoever just took a turn.
  Put them in the `To:` line of your `HANDOFF.md`.
- **Skipping:** if you haven't merged your turn within the skip window, the
  Action passes the turn to the player after you. You sit out that round.
- **Game over:** after the last round, the Action opens a "Game over" issue
  instead of another turn.
- **Joining mid-game:** the host adds new players to the bottom of the list.
  They come up the next time the rotation reaches them.
