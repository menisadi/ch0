# ch0 - Blindfold Chess CLI

A minimal terminal game for playing blindfold chess against built-in engines.

- Install it as a standalone CLI tool
- Play by entering SAN moves (`e4`, `Nf3`, `exd5`, `a8=Q`) plus a handful of helpful commands (`show`, `fen`, `pgn`, …)
- Includes bundled engines (Sunfish, Andoma) and a “bring your own UCI engine” mode

---

## Install

### With uv (recommended)

```bash
uv tool install play-ch0
```

### With pip
```bash
python -m pip install --upgrade play-ch0
````

> Requires **Python 3.13+**.

---

## Run

After installing, you can launch the game with either entrypoint:

```bash
ch0
# or
play-ch0
```

You’ll start in a lobby where you pick an engine + color, then `start`.

---

## Quick start gameplay

- Enter **SAN moves**: `e4`, `Nf3`, `exd5`, `a8=Q`, …
- Or enter **commands** like:

  * `show` - show the board (useful if you “peek”)
  * `moves` - list moves
  * `fen` - print current FEN
  * `pgn` - print current PGN (also printed at game end)
  * `resign` - resign
  * `help` - show available commands
  * `quit` - exit

Commands can also be prefixed with `:` (e.g. `:show`).

The engine moves automatically on its turn.

---

## Opening book (optional)

If you place a Polyglot opening book file named `book.bin` in the **current working directory** when you run `ch0`,
the game will use it for opening-book moves.

---

## Engines

Available options:

- `random` - plays random legal moves
- `andoma` - bundled engine
- `sunfish` - bundled engine
- `uci` - use any external UCI engine (e.g., Stockfish) by providing a command/path; played via `python-chess`

Notes:

- Sunfish and Andoma are third-party projects vendored under `src/ch0/engines/`. I don’t create or maintain them.
- On Windows, ANSI colors work better if `colorama` is installed (it’s auto-used when present).

---

## Development (from source)

If you want to hack on the repo instead of installing from PyPI:

```bash
git clone https://github.com/menisadi/ch0
cd ch0
uv sync
uv run ch0
```

---

## Licenses / third-party

- This project is licensed under **GPLv3** (see `LICENSE`).
- Sunfish is distributed under the GNU General Public License; see `src/ch0/engines/sunfish/LICENSE.md`.
- Andoma is distributed under the MIT License; see `src/ch0/engines/andoma/LICENSE`.

---

## TODO

- [ ] Fix turn bookkeeping - remove `game.turn` and rely on `board.turn`
- [ ] Update move numbering / PGN formatting using `board.turn` before pushing moves
- [ ] Sunfish: validate emitted UCI move is legal
- [ ] Make Polyglot book usage optional
- [ ] Show a subtle “(book)” indicator when a book move is used
- [ ] Add `undo` (at least one ply)
- [ ] Add `status` / `check` command that reports check-like info
- [ ] Decide and implement draw policy: claimable vs automatic handling of draws
- [ ] Add optional PGN autosave to a file (date/engine/color in file-name)
- [ ] Add "illegal moves" count (printed at the end)
- [ ] Add Stockfish bundling or automatic UCI discovery
