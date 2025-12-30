from datetime import date
from pathlib import Path

import chess
import pytest

from ch0 import cli


def make_game(
    *,
    player_color: chess.Color = chess.WHITE,
    engine_kind: str = "random",
    engine_name: str = "random",
    book_path: str | None = None,
    book_chance: float = 0.0,
) -> cli.Game:
    return cli.Game(
        engine_kind=engine_kind,
        engine_name=engine_name,
        player_color=player_color,
        engine=None,
        verbose=False,
        book_path=book_path,
        book_chance=book_chance,
    )


def force_choice(monkeypatch: pytest.MonkeyPatch, move: chess.Move) -> None:
    monkeypatch.setattr(cli.random, "choice", lambda _: move)


def test_bot_makes_a_move_updates_pgn_and_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game()
    move = chess.Move.from_uci("e2e4")
    force_choice(monkeypatch, move)

    cli.bot_makes_a_move(game)

    assert game.board.peek() == move
    assert game.count == 1
    assert game.turn == chess.BLACK
    assert "\n1. e4" in game.pgn_text


def test_bot_makes_a_move_appends_black_move(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game()
    game.board.push_san("e4")
    game.turn = chess.BLACK
    game.count = 1
    game.pgn_text = "\n1. e4"
    move = chess.Move.from_uci("e7e5")
    force_choice(monkeypatch, move)

    cli.bot_makes_a_move(game)

    assert game.count == 1
    assert game.pgn_text.endswith(" e5")


def test_bot_makes_a_move_sets_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game()
    game.board = chess.Board("7k/8/8/8/8/8/8/7K w - - 0 1")
    move = next(iter(game.board.legal_moves))
    force_choice(monkeypatch, move)

    cli.bot_makes_a_move(game)

    assert game.ended is True
    assert "The game is a draw" in game.pgn_text


def test_bot_makes_a_move_sets_checkmate(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game(player_color=chess.WHITE)
    game.board = chess.Board("7k/5Q2/7K/8/8/8/8/8 w - - 0 1")
    mate_move = chess.Move.from_uci("f7g7")
    assert any(mate_move == move for move in game.board.legal_moves)
    force_choice(monkeypatch, mate_move)

    cli.bot_makes_a_move(game)

    assert game.ended is True
    assert game.board.is_checkmate()
    assert "black wins by checkmate" in game.pgn_text


def test_is_a_draw_stalemate() -> None:
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    is_draw, reason = cli.is_a_draw(board)
    assert is_draw is True
    assert reason == "Stalemate"


def test_is_a_draw_insufficient_material() -> None:
    board = chess.Board("7k/8/8/8/8/8/8/7K w - - 0 1")
    is_draw, reason = cli.is_a_draw(board)
    assert is_draw is True
    assert reason == "Insufficient Material"


def test_is_a_draw_fifty_move_rule() -> None:
    board = chess.Board("7k/8/8/8/8/8/8/R6K w - - 100 1")
    is_draw, reason = cli.is_a_draw(board)
    assert is_draw is True
    assert reason == "Fifty-move rule"


def test_is_a_draw_threefold_repetition() -> None:
    board = chess.Board()
    repeat = ["g1f3", "g8f6", "f3g1", "f6g8"]
    for _ in range(2):
        for uci in repeat:
            board.push(chess.Move.from_uci(uci))

    is_draw, reason = cli.is_a_draw(board)
    assert is_draw is True
    assert reason == "Threefold repetition"


def test_finalize_pgn_headers() -> None:
    game_pgn = cli.finalize_pgn("1. e4 e5", chess.WHITE, "sunfish")
    headers = game_pgn.headers

    assert headers["Event"] == "Blind-chess match"
    assert headers["Site"] == "Terminal"
    assert headers["White"] == "Me"
    assert headers["Black"] == "sunfish Bot"
    assert headers["Date"] == date.today().isoformat()


def test_parse_command_and_slugify() -> None:
    assert cli.parse_command(":show") == "show"
    assert cli.parse_command("  MoVes ") == "moves"
    assert cli.parse_command("") is None

    assert cli._slugify_filename("My Bot 2!") == "my_bot_2"
    assert cli._slugify_filename("   ") == "bot"


def test_book_status_line(tmp_path: Path) -> None:
    assert cli._book_status_line(None, 0.5) == "Opening book: none"
    assert cli._book_status_line("missing.bin", 0.5) == "Opening book: none"

    book = tmp_path / "book.bin"
    book.write_bytes(b"")
    assert cli._book_status_line(str(book), 0.5) == f"Opening book: {book} (50%)"


def test_cpl_helpers() -> None:
    empty = {
        "inaccuracies": 0,
        "mistakes": 0,
        "blunders": 0,
        "cpl": 0,
        "moves": 0,
        "worst_loss": -1,
        "worst_san": "",
        "worst_move_number": 0,
        "worst_is_white": True,
    }
    assert cli._average_cpl(empty) == 0
    assert cli._format_worst_move(empty) == "Worst move: n/a"

    entry = {
        **empty,
        "moves": 1,
        "cpl": 120,
        "worst_loss": 120,
        "worst_san": "Nf3",
        "worst_move_number": 3,
    }
    assert cli._average_cpl(entry) == 120
    assert cli._format_worst_move(entry) == "Worst move: 3. Nf3 (120 CPL)"
