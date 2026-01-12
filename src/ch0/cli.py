#!/usr/bin/env -S uv run
import argparse
import random
import subprocess
import io
import os
import shlex
from datetime import date, datetime

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
        verbose: bool = False,
        book_path: str | None = None,
        book_chance: float = 0.5,
    ):
        self.board = chess.Board()
        self.engine_kind = engine_kind  # "random", "andoma", "sunfish", "uci"
        self.engine_name = engine_name
        self.player_color = player_color
        self.engine = engine
        self.verbose = verbose
        self.book_path = book_path
        self.book_chance = book_chance
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
    used_book = False

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
    roll = random.random()
    if game.book_path and game.count < 15 and roll < game.book_chance:
        try:
            with chess.polyglot.open_reader(game.book_path) as reader:
                move = reader.weighted_choice(board).move
                used_book = True
        except (IndexError, FileNotFoundError):
            pass

    turn_number = board.fullmove_number
    move_san = board.san(move)
    board.push(move)

    if game.turn == chess.WHITE:
        game.count += 1
        game.pgn_text += f"\n{game.count}. {move_san}"
    else:
        game.pgn_text += f" {move_san}"

    # Minimal engine output (colored, no label)
    turn_prefix = c(f"{turn_number}.", Style.DIM)
    if game.verbose and used_book:
        print(
            f"{turn_prefix} {c(move_san, Style.MAGENTA, Style.BOLD)}"
            f"{c(' (book)', Style.DIM)}"
        )
    else:
        print(f"{turn_prefix} {c(move_san, Style.MAGENTA, Style.BOLD)}")

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


def _book_status_line(book_path: str | None, book_chance: float) -> str:
    if book_path is None:
        return "Opening book: none"
    if os.path.exists(book_path):
        chance_pct = round(book_chance * 100)
        return f"Opening book: {book_path} ({chance_pct}%)"
    return "Opening book: none"


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
    print(f"  {c('quick', Style.CYAN)}  start with sunfish + random color")
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


def _parse_player_move(board: chess.Board, user_in: str) -> chess.Move | None:
    try:
        move = board.parse_san(user_in)
    except ValueError:
        return None
    if "x" in user_in and not board.is_capture(move):
        return None
    return move


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


def _slugify_filename(text: str) -> str:
    cleaned = []
    for ch in text.strip().lower():
        if ch.isalnum() or ch in {"-", "_"}:
            cleaned.append(ch)
        elif ch.isspace():
            cleaned.append("_")
    return "".join(cleaned) or "bot"


def ask_pgn_action() -> str:
    prompt = "Final PGN: (p)rint, (s)ave, or (n)one?"
    suffix = " [n]: "
    while True:
        ans = input(c(prompt + suffix, Style.DIM)).strip().lower()
        if not ans:
            return "none"
        if ans in {"p", "print"}:
            return "print"
        if ans in {"s", "save"}:
            return "save"
        if ans in {"n", "no", "none", "skip"}:
            return "none"
        print(c("Please answer print, save, or skip.", Style.RED))


def _score_to_cp(score: chess.engine.PovScore) -> int:
    return score.score(mate_score=100000)


def _summarize_cpl(loss_cp: int) -> str:
    return f"{loss_cp} CPL"


def _analyze_pgn_with_stockfish(
    game_pgn: chess.pgn.Game,
    stockfish_cmd: str,
) -> dict[chess.Color, dict[str, int | str | bool]] | None:
    cmd = stockfish_cmd.strip() or "stockfish"
    engine = _spawn_uci_engine(cmd)
    if engine is None:
        return None

    stats = {
        chess.WHITE: {
            "inaccuracies": 0,
            "mistakes": 0,
            "blunders": 0,
            "cpl": 0,
            "moves": 0,
            "worst_loss": -1,
            "worst_san": "",
            "worst_move_number": 0,
            "worst_is_white": True,
        },
        chess.BLACK: {
            "inaccuracies": 0,
            "mistakes": 0,
            "blunders": 0,
            "cpl": 0,
            "moves": 0,
            "worst_loss": -1,
            "worst_san": "",
            "worst_move_number": 0,
            "worst_is_white": False,
        },
    }
    board = game_pgn.board()
    limit = chess.engine.Limit(depth=12)

    try:
        for move in game_pgn.mainline_moves():
            mover = board.turn
            move_san = board.san(move)
            move_number = board.fullmove_number
            best_info = engine.analyse(board, limit)
            best_cp = _score_to_cp(best_info["score"].pov(mover))

            played_info = engine.analyse(board, limit, root_moves=[move])
            played_cp = _score_to_cp(played_info["score"].pov(mover))

            loss = max(0, best_cp - played_cp)
            stats[mover]["cpl"] += loss
            stats[mover]["moves"] += 1

            if loss > stats[mover]["worst_loss"]:
                stats[mover]["worst_loss"] = loss
                stats[mover]["worst_san"] = move_san
                stats[mover]["worst_move_number"] = move_number
                stats[mover]["worst_is_white"] = mover == chess.WHITE

            if loss >= 300:
                stats[mover]["blunders"] += 1
            elif loss >= 100:
                stats[mover]["mistakes"] += 1
            elif loss >= 50:
                stats[mover]["inaccuracies"] += 1

            board.push(move)
    finally:
        engine.quit()

    return stats


def ask_stockfish_command() -> str:
    prompt = "Stockfish command/path"
    suffix = " [stockfish]: "
    return input(c(prompt + suffix, Style.DIM)).strip()


def ask_analysis_report() -> str:
    prompt = "Post-game analysis: (s)tats, (a)ccuracy, (w)orst move, (f)ull, or (n)one?"
    suffix = " [n]: "
    while True:
        ans = input(c(prompt + suffix, Style.DIM)).strip().lower()
        if not ans:
            return "none"
        if ans in {"s", "stats"}:
            return "stats"
        if ans in {"a", "accuracy", "avg"}:
            return "accuracy"
        if ans in {"w", "worst"}:
            return "worst"
        if ans in {"f", "full", "report"}:
            return "full"
        if ans in {"n", "no", "none", "skip"}:
            return "none"
        print(c("Please answer stats, accuracy, worst, full, or none.", Style.RED))


def _average_cpl(stats_entry: dict[str, int | str | bool]) -> int:
    moves = int(stats_entry["moves"])
    if moves <= 0:
        return 0
    return round(int(stats_entry["cpl"]) / moves)


def _format_worst_move(stats_entry: dict[str, int | str | bool]) -> str:
    moves = int(stats_entry["moves"])
    if moves <= 0:
        return "Worst move: n/a"
    move_number = int(stats_entry["worst_move_number"])
    move_san = str(stats_entry["worst_san"])
    worst_loss = int(stats_entry["worst_loss"])
    prefix = f"{move_number}. " if bool(stats_entry["worst_is_white"]) else f"{move_number}... "
    return f"Worst move: {prefix}{move_san} ({_summarize_cpl(worst_loss)})"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show a subtle indicator when an opening book move is used.",
    )
    parser.add_argument(
        "--book",
        metavar="PATH",
        default="book.bin",
        help="Path to a Polyglot opening book (default: book.bin).",
    )
    parser.add_argument(
        "--book-chance",
        metavar="P",
        type=float,
        default=0.5,
        help="Chance to use an opening book move when available (0.0-1.0).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = _parse_args(argv)
    print(c("\nBlindfold Chess\n", Style.BOLD))
    print_help()
    print()

    game: Game | None = None

    while True:
        # If a game ended, optionally print PGN, then return to lobby.
        if game is not None and game.ended:
            if game.pgn_text:
                final_pgn = finalize_pgn(game.pgn_text, game.player_color, game.engine_name)
                action = ask_pgn_action()
                if action == "print":
                    print()
                    print(c("Final PGN:", Style.CYAN, Style.BOLD))
                    print(final_pgn)
                elif action == "save":
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    opponent = _slugify_filename(game.engine_name)
                    filename = f"ch0_{opponent}_{stamp}.pgn"
                    with open(filename, "w", encoding="utf-8") as handle:
                        handle.write(str(final_pgn))
                        handle.write("\n")
                    print(c(f"Saved PGN to {filename}", Style.DIM))

                analysis_choice = ask_analysis_report()
                if analysis_choice != "none":
                    stockfish_cmd = ask_stockfish_command()
                    stats = _analyze_pgn_with_stockfish(final_pgn, stockfish_cmd)
                    if stats is None:
                        print(c("Could not start Stockfish.", Style.RED))
                    else:
                        you_color = game.player_color
                        engine_color = not game.player_color
                        you_stats = stats[you_color]
                        engine_stats = stats[engine_color]
                        print()
                        print(c("Post-game analysis:", Style.CYAN, Style.BOLD))
                        if analysis_choice in {"stats", "full"}:
                            print(
                                f"  {c('You:', Style.CYAN)} "
                                f"{you_stats['inaccuracies']} inaccuracies, "
                                f"{you_stats['mistakes']} mistakes, "
                                f"{you_stats['blunders']} blunders"
                            )
                            print(
                                f"  {c(f'{game.engine_name} Bot:', Style.CYAN)} "
                                f"{engine_stats['inaccuracies']} inaccuracies, "
                                f"{engine_stats['mistakes']} mistakes, "
                                f"{engine_stats['blunders']} blunders"
                            )
                        if analysis_choice in {"accuracy", "full"}:
                            print(
                                f"  {c('You:', Style.CYAN)} Avg CPL {_average_cpl(you_stats)}"
                            )
                            print(
                                f"  {c(f'{game.engine_name} Bot:', Style.CYAN)} "
                                f"Avg CPL {_average_cpl(engine_stats)}"
                            )
                        if analysis_choice in {"worst", "full"}:
                            print(
                                f"  {c('You:', Style.CYAN)} "
                                f"{_format_worst_move(you_stats)}"
                            )
                            print(
                                f"  {c(f'{game.engine_name} Bot:', Style.CYAN)} "
                                f"{_format_worst_move(engine_stats)}"
                            )
            game.close_engine()
            game = None
            print()
            print(c("Lobby. Type 'start' or 'quick' to play.", Style.DIM))
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
                game = Game(
                    engine_kind,
                    engine_name,
                    player_color,
                    engine=engine,
                    verbose=args.verbose,
                    book_path=args.book,
                    book_chance=args.book_chance,
                )

                print()
                print(
                    c("You:", Style.DIM)
                    + " "
                    + c(bool_color_to_string(player_color), Style.CYAN, Style.BOLD)
                    + c(" vs ", Style.DIM)
                    + c(engine_name, Style.CYAN, Style.BOLD)
                )
                print(c(_book_status_line(args.book, args.book_chance), Style.DIM))
                print(c("Tip: type 'show' to display the board.", Style.DIM))
                print()

                # If the engine is white, let it move first.
                if player_color == chess.BLACK:
                    bot_makes_a_move(game)
                continue

            if cmd == "quick":
                engine_kind = "sunfish"
                engine_name = "sunfish"
                engine = None
                player_color = random.choice([chess.WHITE, chess.BLACK])
                game = Game(
                    engine_kind,
                    engine_name,
                    player_color,
                    engine=engine,
                    verbose=args.verbose,
                    book_path=args.book,
                    book_chance=args.book_chance,
                )

                print()
                print(
                    c("You:", Style.DIM)
                    + " "
                    + c(bool_color_to_string(player_color), Style.CYAN, Style.BOLD)
                    + c(" vs ", Style.DIM)
                    + c(engine_name, Style.CYAN, Style.BOLD)
                )
                print(c(_book_status_line(args.book, args.book_chance), Style.DIM))
                print(c("Tip: type 'show' to display the board.", Style.DIM))
                print()

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

            print(c("No active game. Type 'start' or 'quick' (or 'help', 'quit').", Style.RED))
            continue

        # If it's engine's turn, just let it move.
        if game.board.turn != game.player_color:
            bot_makes_a_move(game)
            continue

        turn_prompt = f"{game.board.fullmove_number}> "
        user_in = input(c(turn_prompt, Style.DIM)).strip()
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
        move = _parse_player_move(game.board, user_in)
        if move is None:
            print(c("Illegal move / unknown command.", Style.RED))
            continue

        game.board.push(move)

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
