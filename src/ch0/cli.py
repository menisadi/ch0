#!/usr/bin/env -S uv run
import random
import subprocess
import io
import os
import shlex
from datetime import date

import chess
import chess.pgn
import chess.polyglot
import chess.engine

from .engines.andoma.movegeneration import next_move as andoma_gen
from .engines.sunfish import sunfish_uci
from .engines.sunfish.tools import uci


# --- Colors (ANSI) ------------------------------------------------------------
# Works in most terminals. On Windows, ANSI is supported in modern terminals;
# if you need broader support, install `colorama` and it will be used if present.
try:
    import colorama  # type: ignore
    colorama.just_fix_windows_console()
except Exception:
    pass


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def c(text: str, *styles: str) -> str:
    return "".join(styles) + text + Style.RESET


# --- Game logic --------------------------------------------------------------
class Game:
    def __init__(
        self,
        engine_kind: str,
        engine_name: str,
        player_color: chess.Color,
        engine: chess.engine.SimpleEngine | None = None,
    ):
        self.board = chess.Board()
        self.engine_kind = engine_kind  # "random", "andoma", "sunfish", "uci"
        self.engine_name = engine_name
        self.player_color = player_color
        self.engine = engine
        self.turn = chess.WHITE  # whose turn it is to move in our bookkeeping
        self.count = 0           # move number (full moves)
        self.pgn_text = ""
        self.ended = False

    def reset(self):
        self.board.set_fen(chess.STARTING_FEN)
        self.turn = chess.WHITE
        self.count = 0
        self.pgn_text = ""
        self.ended = False

    def close_engine(self):
        if self.engine is None:
            return
        try:
            self.engine.quit()
        except Exception:
            try:
                self.engine.close()
            except Exception:
                pass
        self.engine = None


def is_a_draw(board: chess.Board):
    """Return (is_draw, message)."""
    if board.is_stalemate():
        return True, "Stalemate"
    elif board.is_insufficient_material():
        return True, "Insufficient Material"
    elif board.can_claim_fifty_moves():
        return True, "Fifty-move rule"
    elif board.can_claim_threefold_repetition():
        return True, "Threefold repetition"
    return False, ""


def bool_color_to_string(color_b: chess.Color) -> str:
    return "white" if color_b == chess.WHITE else "black"


def finalize_pgn(pgn_str: str, player_color: chess.Color, engine_name: str):
    final_pgn = pgn_str + "\n\n"
    game_pgn = chess.pgn.read_game(io.StringIO(final_pgn))
    game_pgn.headers["Event"] = "Blind-chess match"
    game_pgn.headers["Site"] = "Terminal"
    if player_color == chess.WHITE:
        game_pgn.headers["White"] = "Me"
        game_pgn.headers["Black"] = f"{engine_name} Bot"
    else:
        game_pgn.headers["White"] = f"{engine_name} Bot"
        game_pgn.headers["Black"] = "Me"
    game_pgn.headers["Date"] = date.today().isoformat()
    return game_pgn


def bot_makes_a_move(game: Game):
    board = game.board
    move = random.choice(list(board.legal_moves))

    if game.engine_kind == "andoma":
        move = andoma_gen(depth=4, board=board, debug=False)
    elif game.engine_kind == "sunfish":
        position = uci.from_fen(*board.fen().split())
        current_hist = (
            [position]
            if uci.get_color(position) == uci.WHITE
            else [position.rotate(), position]
        )
        total_time = random.randint(10, 60)
        _, uci_move_str = sunfish_uci.generate_move(current_hist, total_time)
        move = chess.Move.from_uci(uci_move_str)
    elif game.engine_kind == "uci":
        if game.engine is None:
            raise RuntimeError("UCI engine is not initialized.")
        think_time = random.uniform(0.1, 0.5)
        result = game.engine.play(board, chess.engine.Limit(time=think_time))
        move = result.move

    # optional opening book
    coin = random.randint(0, 1)
    if game.count < 15 and coin == 1:
        try:
            with chess.polyglot.open_reader("book.bin") as reader:
                move = reader.weighted_choice(board).move
        except (IndexError, FileNotFoundError):
            pass

    move_san = board.san(move)
    board.push(move)

    if game.turn == chess.WHITE:
        game.count += 1
        game.pgn_text += f"\n{game.count}. {move_san}"
    else:
        game.pgn_text += f" {move_san}"

    # Minimal engine output (colored, no label)
    print(c(move_san, Style.MAGENTA, Style.BOLD))

    # draw / checkmate handling
    check_draw, draw_type = is_a_draw(board)
    if check_draw:
        print(c(f"Draw: {draw_type}", Style.YELLOW, Style.BOLD))
        game.pgn_text += " { The game is a draw. } 1/2-1/2"
        game.ended = True
        return

    if board.is_checkmate():
        print(c("Checkmate.", Style.RED, Style.BOLD))
        result = "0-1" if game.player_color == chess.WHITE else "1-0"
        game.pgn_text += (
            f" {{ {bool_color_to_string(not game.player_color)} wins by checkmate. }} "
            f"{result}"
        )
        game.ended = True
        return

    game.turn = not game.turn


def _engine_display_name(command: str, engine: chess.engine.SimpleEngine) -> str:
    name = engine.id.get("name")
    if name:
        return name
    return os.path.basename(command.split()[0]) or "UCI"


def _spawn_uci_engine(command: str) -> chess.engine.SimpleEngine | None:
    cmd = shlex.split(command)
    if not cmd:
        return None
    try:
        return chess.engine.SimpleEngine.popen_uci(cmd, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, PermissionError, OSError, chess.engine.EngineError):
        return None


def choose_engine() -> tuple[str, str, chess.engine.SimpleEngine | None]:
    options = ["random", "andoma", "sunfish", "uci"]
    print(c("Choose engine:", Style.CYAN, Style.BOLD))
    for i, name in enumerate(options, start=1):
        print(f"  {c(str(i) + '.', Style.DIM)} {c(name, Style.CYAN)}")
    while True:
        choice = input(c("engine> ", Style.DIM)).strip().lower()
        if choice in {"1", "2", "3", "4"}:
            choice = options[int(choice) - 1]
        if choice in options:
            if choice != "uci":
                return choice, choice, None
            while True:
                cmd = input(c("uci engine path/command> ", Style.DIM)).strip()
                engine = _spawn_uci_engine(cmd)
                if engine is not None:
                    display_name = _engine_display_name(cmd, engine)
                    return "uci", display_name, engine
                print(c("Could not start engine. Try again.", Style.RED))
        print(c("Invalid choice.", Style.RED))


def choose_color():
    print(c("Choose your color:", Style.CYAN, Style.BOLD))
    print(f"  {c('1.', Style.DIM)} {c('white', Style.CYAN)}")
    print(f"  {c('2.', Style.DIM)} {c('black', Style.CYAN)}")
    print(f"  {c('3.', Style.DIM)} {c('random', Style.CYAN)}")
    while True:
        choice = input(c("color> ", Style.DIM)).strip().lower()
        if choice in {"1", "white"}:
            return chess.WHITE
        if choice in {"2", "black"}:
            return chess.BLACK
        if choice in {"3", "random"}:
            return random.choice([chess.WHITE, chess.BLACK])
        print(c("Invalid choice.", Style.RED))


def print_help():
    print(c("Lobby:", Style.CYAN, Style.BOLD))
    print(f"  {c('start', Style.CYAN)}  start a new game")
    print(f"  {c('help', Style.CYAN)}   show this help")
    print(f"  {c('quit', Style.CYAN)}   quit")
    print()
    print(c("In-game:", Style.CYAN, Style.BOLD))
    print(f"  {c('show', Style.CYAN)}   show the board")
    print(f"  {c('moves', Style.CYAN)}  show legal moves (SAN)")
    print(f"  {c('fen', Style.CYAN)}    show FEN")
    print(f"  {c('pgn', Style.CYAN)}    show PGN so far")
    print(f"  {c('resign', Style.CYAN)} resign the game")
    print()
    print(c("Or type a move in SAN, e.g. e4, Nf3, exd5, a8=Q.", Style.DIM))


def parse_command(s: str):
    """Normalize commands: ':show' and 'show' both become 'show'."""
    s = s.strip()
    if not s:
        return None
    if s.startswith(":"):
        s = s[1:]
    return s.lower()


def ask_yes_no(prompt: str, default_no: bool = True) -> bool:
    suffix = " [y/N]: " if default_no else " [Y/n]: "
    while True:
        ans = input(c(prompt + suffix, Style.DIM)).strip().lower()
        if not ans:
            return not default_no
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print(c("Please answer y or n.", Style.RED))


def main():
    print(c("\nBlindfold Chess\n", Style.BOLD))
    print_help()
    print()

    game: Game | None = None

    while True:
        # If a game ended, optionally print PGN, then return to lobby.
        if game is not None and game.ended:
            if game.pgn_text and ask_yes_no("Print final PGN?", default_no=True):
                print()
                print(c("Final PGN:", Style.CYAN, Style.BOLD))
                print(finalize_pgn(game.pgn_text, game.player_color, game.engine_name))
            game.close_engine()
            game = None
            print()
            print(c("Lobby. Type 'start' to play.", Style.DIM))
            continue

        # No active game: only limited commands work.
        if game is None:
            user_in = input(c("> ", Style.DIM)).strip()
            if not user_in:
                continue

            cmd = parse_command(user_in)
            if cmd == "start":
                engine_kind, engine_name, engine = choose_engine()
                player_color = choose_color()
                game = Game(engine_kind, engine_name, player_color, engine=engine)

                print()
                print(
                    c("You:", Style.DIM)
                    + " "
                    + c(bool_color_to_string(player_color), Style.CYAN, Style.BOLD)
                    + c(" vs ", Style.DIM)
                    + c(engine_name, Style.CYAN, Style.BOLD)
                )
                print(c("Tip: type 'show' to display the board.", Style.DIM))
                print()

                # If the engine is white, let it move first.
                if player_color == chess.BLACK:
                    bot_makes_a_move(game)
                continue

            if cmd == "help":
                print_help()
                print()
                continue

            if cmd == "quit":
                print(c("Goodbye.", Style.DIM))
                if game is not None:
                    game.close_engine()
                break

            print(c("No active game. Type 'start' (or 'help', 'quit').", Style.RED))
            continue

        # If it's engine's turn, just let it move.
        if game.board.turn != game.player_color:
            bot_makes_a_move(game)
            continue

        user_in = input(c("> ", Style.DIM)).strip()
        if not user_in:
            continue

        cmd = parse_command(user_in)

        # Known in-game commands
        if cmd in {"help", "show", "moves", "fen", "pgn", "resign", "quit", "start"}:
            if cmd == "help":
                print_help()
            elif cmd == "show":
                print(game.board)
            elif cmd == "moves":
                moves_in_uci = list(game.board.legal_moves)
                moves_in_san = [game.board.san(m) for m in moves_in_uci]
                print(" ".join(moves_in_san))
            elif cmd == "fen":
                print(game.board.fen())
            elif cmd == "pgn":
                print(finalize_pgn(game.pgn_text, game.player_color, game.engine_name))
            elif cmd == "resign":
                print(c("Resigned.", Style.YELLOW, Style.BOLD))
                result = "0-1" if game.player_color == chess.WHITE else "1-0"
                game.pgn_text += (
                    f" {{ {bool_color_to_string(game.player_color)} resigns. }} {result}"
                )
                game.ended = True
            elif cmd == "quit":
                print(c("Goodbye.", Style.DIM))
                game.close_engine()
                break
            elif cmd == "start":
                print(c("Game in progress. Finish or resign first.", Style.RED))
            continue

        # Otherwise, try to interpret it as a move in SAN
        try:
            game.board.push_san(user_in)
        except ValueError:
            print(c("Illegal move / unknown command.", Style.RED))
            continue

        # Optional: extremely subtle acknowledgement (comment out if you want *zero* noise)
        # print(c("✓", Style.GREEN, Style.DIM))

        if game.turn == chess.WHITE:
            game.count += 1
            game.pgn_text += f"\n{game.count}. {user_in}"
        else:
            game.pgn_text += f" {user_in}"

        check_draw, draw_type = is_a_draw(game.board)
        if check_draw:
            print(c(f"Draw: {draw_type}", Style.YELLOW, Style.BOLD))
            game.pgn_text += " { The game is a draw. } 1/2-1/2"
            game.ended = True
            continue

        if game.board.is_checkmate():
            print(c("Checkmate. You win.", Style.GREEN, Style.BOLD))
            result = "1-0" if game.player_color == chess.WHITE else "0-1"
            game.pgn_text += (
                f" {{ {bool_color_to_string(game.player_color)} wins by checkmate. }} "
                f"{result}"
            )
            game.ended = True
            continue

        game.turn = not game.turn
        # engine will move in the next iteration


if __name__ == "__main__":
    main()
