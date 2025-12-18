#!/usr/bin/env -S uv run
import random
import io
from datetime import date

import chess
import chess.pgn
import chess.polyglot

from Engines.andoma.movegeneration import next_move as andoma_gen
from Engines.sunfish import sunfish_uci
from Engines.sunfish.tools import uci


class Game:
    def __init__(self, engine_name: str, player_color: chess.Color):
        self.board = chess.Board()
        self.engine_name = engine_name  # "random", "andoma", "sunfish"
        self.player_color = player_color
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

    if game.engine_name == "andoma":
        move = andoma_gen(depth=4, board=board, debug=False)
    elif game.engine_name == "sunfish":
        position = uci.from_fen(*board.fen().split())
        current_hist = (
            [position]
            if uci.get_color(position) == uci.WHITE
            else [position.rotate(), position]
        )
        total_time = random.randint(10, 60)
        _, uci_move_str = sunfish_uci.generate_move(current_hist, total_time)
        move = chess.Move.from_uci(uci_move_str)

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

    print(f"Engine plays: {move_san}")

    # draw / checkmate handling
    check_draw, draw_type = is_a_draw(board)
    if check_draw:
        print(f"Draw: {draw_type}")
        game.pgn_text += " { The game is a draw. } 1/2-1/2"
        game.ended = True
        return

    if board.is_checkmate():
        print("Game over – engine wins.")
        # result from White/Black perspective
        result = "0-1" if game.player_color == chess.WHITE else "1-0"
        game.pgn_text += (
            f" {{ {bool_color_to_string(not game.player_color)} wins by checkmate. }} "
            f"{result}"
        )
        game.ended = True
        return

    game.turn = not game.turn


def choose_engine():
    options = ["random", "andoma", "sunfish"]
    print("Choose engine:")
    for i, name in enumerate(options, start=1):
        print(f"  {i}. {name}")
    while True:
        choice = input("Engine [1-3 or name]: ").strip().lower()
        if choice in {"1", "2", "3"}:
            return options[int(choice) - 1]
        if choice in options:
            return choice
        print("Invalid choice.")


def choose_color():
    print("Choose your color:")
    print("  1. white")
    print("  2. black")
    print("  3. random")
    while True:
        choice = input("Color [1-3 or name]: ").strip().lower()
        if choice in {"1", "white"}:
            return chess.WHITE
        if choice in {"2", "black"}:
            return chess.BLACK
        if choice in {"3", "random"}:
            return random.choice([chess.WHITE, chess.BLACK])
        print("Invalid choice.")


def print_help():
    print("Lobby commands:")
    print("  start  - start a new game (choose engine and color)")
    print("  help   - show this help")
    print("  quit   - quit")
    print("")
    print("In-game commands:")
    print("  show   - show the board")
    print("  moves  - show legal moves (SAN)")
    print("  fen    - show FEN")
    print("  pgn    - show PGN so far")
    print("  resign - resign the game")
    print("")
    print("Or just type a move in SAN, e.g. e4, Nf3, exd5, a8=Q.")


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
        ans = input(prompt + suffix).strip().lower()
        if not ans:
            return not default_no
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please answer y or n.")


def main():
    print("=== Blindfold Chess – Terminal Edition ===")
    print_help()
    print()

    game: Game | None = None

    while True:
        # If a game ended, optionally print PGN, then return to lobby.
        if game is not None and game.ended:
            if game.pgn_text and ask_yes_no("Print final PGN?", default_no=True):
                print("\nFinal PGN:")
                print(finalize_pgn(game.pgn_text, game.player_color, game.engine_name))
            game = None
            print("\nBack to lobby. Type 'start' to begin a new game.")
            continue

        # No active game: only limited commands work.
        if game is None:
            user_in = input("Command (start/help/quit): ").strip()
            if not user_in:
                continue

            cmd = parse_command(user_in)
            if cmd == "start":
                engine_name = choose_engine()
                player_color = choose_color()
                game = Game(engine_name, player_color)
                print(f"\nYou are playing {bool_color_to_string(player_color)} "
                      f"against the {engine_name} engine.\n")
                print("Type 'show' to display the board at any time.\n")

                # If the engine is white, let it move first.
                if player_color == chess.BLACK:
                    bot_makes_a_move(game)
                continue

            if cmd == "help":
                print_help()
                continue

            if cmd == "quit":
                print("Goodbye.")
                break

            print("No active game. Use 'start' to begin or 'help' for options.")
            continue

        # If it's engine's turn, just let it move.
        if game.board.turn != game.player_color:
            bot_makes_a_move(game)
            continue

        user_in = input("Your move (or command): ").strip()
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
                print("Legal moves:", " ".join(moves_in_san))
            elif cmd == "fen":
                print(game.board.fen())
            elif cmd == "pgn":
                print(finalize_pgn(game.pgn_text, game.player_color, game.engine_name))
            elif cmd == "resign":
                print("You resigned.")
                result = "0-1" if game.player_color == chess.WHITE else "1-0"
                game.pgn_text += (
                    f" {{ {bool_color_to_string(game.player_color)} resigns. }} {result}"
                )
                game.ended = True
            elif cmd == "quit":
                print("Goodbye.")
                break
            elif cmd == "start":
                print("Nope 🙂 A game is already in progress. Resign or finish it first.")
            continue

        # Otherwise, try to interpret it as a move in SAN
        try:
            game.board.push_san(user_in)
        except ValueError:
            print(f"'{user_in}' is not a legal SAN move or command. Type 'help' for options.")
            continue

        if game.turn == chess.WHITE:
            game.count += 1
            game.pgn_text += f"\n{game.count}. {user_in}"
        else:
            game.pgn_text += f" {user_in}"

        check_draw, draw_type = is_a_draw(game.board)
        if check_draw:
            print(f"Draw: {draw_type}")
            game.pgn_text += " { The game is a draw. } 1/2-1/2"
            game.ended = True
            continue

        if game.board.is_checkmate():
            print("Game over – you win!")
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
