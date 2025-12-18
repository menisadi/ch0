# Blindfold Chess CLI

Minimal terminal game for playing blindfold chess against built-in engines.

## Quick start
- Install deps with `uv sync` (Python 3.13+).
- Run the game: `uv run main.py` and follow the prompts to pick an engine and color.
- Optional: place `book.bin` in the repo root to enable opening-book moves.

## Gameplay
- Play blindfolded in the terminal: enter SAN moves (`e4`, `Nf3`, `exd5`, `a8=Q`) or commands like `show`, `moves`, `fen`, `pgn`, `resign`.
- Start from the lobby with `start`, choose engine and color; the bot moves automatically on its turn.
- PGN is built as you play; you can print it when the game ends.

## Dependencies
- Python 3.13+ with `uv` for managing the virtualenv (`uv sync`).
- Runtime: `python-chess`; optional `colorama` for Windows ANSI colors.
- Optional data: `book.bin` opening book in the repo root.

## Engines
- Includes the open-source Sunfish and Andoma engines under `Engines/`; they are third-party projects I do not create or maintain.

## PLans
- [ ] Add stockfish
