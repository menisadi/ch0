from types import SimpleNamespace

import pytest

from ch0 import cli


def feed_inputs(monkeypatch: pytest.MonkeyPatch, inputs: list[str]) -> None:
    iterator = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda _: next(iterator))


def test_ask_yes_no_defaults_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_inputs(monkeypatch, ["", "y"])
    assert cli.ask_yes_no("Confirm?") is False

    feed_inputs(monkeypatch, ["maybe", "Y"])
    assert cli.ask_yes_no("Confirm?") is True


def test_ask_pgn_action_defaults_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_inputs(monkeypatch, [""])
    assert cli.ask_pgn_action() == "none"

    feed_inputs(monkeypatch, ["wat", "s"])
    assert cli.ask_pgn_action() == "save"


def test_ask_analysis_report_defaults_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_inputs(monkeypatch, [""])
    assert cli.ask_analysis_report() == "none"

    feed_inputs(monkeypatch, ["nope", "full"])
    assert cli.ask_analysis_report() == "full"


def test_engine_display_name_falls_back_to_command() -> None:
    engine = SimpleNamespace(id={"name": "Stockfish"})
    assert cli._engine_display_name("stockfish", engine) == "Stockfish"

    unnamed = SimpleNamespace(id={})
    assert cli._engine_display_name("/usr/bin/fish", unnamed) == "fish"


def test_spawn_uci_engine_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(cli.chess.engine.SimpleEngine, "popen_uci", boom)
    assert cli._spawn_uci_engine("missing-engine") is None


def test_main_start_resign_quit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    feed_inputs(
        monkeypatch,
        [
            "start",
            "1",
            "1",
            "resign",
            "",
            "",
            "quit",
        ],
    )

    cli.main([])

    out = capsys.readouterr().out
    assert "Resigned." in out
    assert "Goodbye." in out
