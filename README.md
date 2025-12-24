# ch0 - Blindfold Chess CLI

Minimal terminal game for playing blindfold chess against built-in engines.

## Quick start

- Install deps with `uv sync` (Python 3.13+).
- Run the game: `uv run ch0` and follow the prompts to pick an engine and color.
- Optional: place `book.bin` in the repo root to enable opening-book moves.

## Gameplay

- Play blindfolded in the terminal: enter SAN moves (`e4`, `Nf3`, `exd5`, `a8=Q`) or commands like `show`, `moves`, `fen`, `pgn`, `resign`.
- Start from the lobby with `start`, choose engine and color; the bot moves automatically on its turn.
- Use `help` in the lobby or in-game to list commands; `quit` exits.
- Commands can be prefixed with `:` (e.g., `:show`).
- PGN is built as you play; you can print it when the game ends.

## Dependencies
- Python 3.13+ with `uv` for managing the virtualenv (`uv sync`).
- Runtime: `python-chess`; optional `colorama` for Windows ANSI colors (auto-enabled if installed).
- Optional data: `book.bin` opening book in the repo root.

## Engines

- Options: `random`, `andoma`, `sunfish`, or `uci`.
- UCI lets you provide a path/command to any UCI engine (e.g., Stockfish) and plays via `python-chess`.
- Includes the open-source Sunfish and Andoma engines under `src/ch0/engines/`; they are third-party projects I do not create or maintain.

## Third-party licenses

- Sunfish is distributed under the GNU General Public License; see `src/ch0/engines/sunfish/LICENSE.md`.
- Andoma is distributed under the MIT License; see `src/ch0/engines/andoma/LICENSE`.

## TODO

- [ ] Fix turn bookkeeping - Remove `game.turn` and rely on `board.turn`
- [ ] Update move numbering / PGN formatting using `board.turn` before pushing moves
- [ ] Sunfish: validate emitted UCI move is legal
- [ ] Make Polyglot book usage optional
- [ ] Show a subtle “(book)” indicator when a book move is used
- [ ] Add `undo` (at least one ply)
- [ ] Add `status` / `check` command that reports check-like info
- [ ] Decide and implement draw policy: claimable vs automatic handling of draws
- [ ] Add optional PGN autosave to a file (date/engine/color in file-name)
- [ ] Add "illegal moves" count (which will be printed at the end)
- [ ] Add Stockfish bundling or automatic UCI discovery
