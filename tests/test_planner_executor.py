"""Tests for the planner and executor (including resume)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photo_organizer.config import Config, Operation
from photo_organizer.database import Database
from photo_organizer.models import Event, MediaFile, MediaKind
from photo_organizer.organizer import Executor, Planner


def _make_media(src: Path, when: datetime | None) -> MediaFile:
    return MediaFile(
        path=src,
        kind=MediaKind.PHOTO,
        size=src.stat().st_size,
        file_hash=src.name,
        capture_date=when,
    )


def _config(tmp_path: Path, op: Operation = Operation.COPY) -> Config:
    return Config.from_dict(
        {
            "source_dir": str(tmp_path / "src"),
            "target_dir": str(tmp_path / "out"),
            "operation": op.value,
            "language": "de",
        }
    )


def test_plan_builds_year_month_event(tmp_path: Path) -> None:
    src = tmp_path / "src" / "a.jpg"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"data")
    event = Event(event_id=1, name="Strand", files=[_make_media(src, datetime(2022, 7, 4))])
    plan = Planner(_config(tmp_path)).build([event])
    entry = plan.entries[0]
    parts = entry.target.parts
    assert "2022" in parts
    assert "07 Juli" in parts
    assert "Strand" in parts
    tree = plan.target_root_tree()
    assert tree["2022"]["07 Juli"]["Strand"] == 1


def test_executor_copies_and_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "src" / "a.jpg"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"data")
    cfg = _config(tmp_path, Operation.COPY)
    event = Event(event_id=1, name="Event 01", files=[_make_media(src, datetime(2022, 7, 4))])
    plan = Planner(cfg).build([event])

    with Database(tmp_path / "db.sqlite") as db:
        executor = Executor(db, Operation.COPY)
        result = executor.execute(plan)
        assert result.copied == 1
        assert plan.entries[0].target.exists()
        assert src.exists()  # copy keeps the source

        # Re-running should skip the already-placed file.
        result2 = executor.execute(plan)
        assert result2.skipped == 1


def test_executor_move_and_resume(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    files = []
    for i in range(3):
        p = src_dir / f"f{i}.jpg"
        p.write_bytes(b"x")
        files.append(_make_media(p, datetime(2021, 1, 1)))
    cfg = _config(tmp_path, Operation.MOVE)
    event = Event(event_id=1, name="Event 01", files=files)
    plan = Planner(cfg).build([event])

    db_path = tmp_path / "db.sqlite"
    # First run: stop after the first file to simulate an interruption.
    with Database(db_path) as db:
        executor = Executor(db, Operation.MOVE)
        state = {"n": 0}

        def stop() -> bool:
            state["n"] += 1
            return state["n"] > 1

        executor.execute(plan, should_stop=stop)

    # Resume: the remaining files should be processed.
    with Database(db_path) as db:
        executor = Executor(db, Operation.MOVE)
        result = executor.resume()
        assert result.moved + result.skipped >= 1
    moved = list((tmp_path / "out").rglob("*.jpg"))
    assert len(moved) == 3
