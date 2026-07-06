"""End-to-end pipeline test using the metadata-only (null AI) backend."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from photo_organizer.config import Config
from photo_organizer.database import Database
from photo_organizer.pipeline import Pipeline


def _config(tmp_path: Path, src: Path) -> Config:
    return Config.from_dict(
        {
            "source_dir": str(src),
            "target_dir": str(tmp_path / "out"),
            "operation": "copy",
            "language": "de",
            "ai": {"enabled": False, "backend": "null"},
            "geo": {"enabled": False},
            "performance": {"workers": 2},
        }
    )


def test_full_run(make_image: Callable[..., Path], tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    # File names carry parseable dates so clustering is deterministic offline.
    make_image("src/2022-07-04_10-00-00_a.jpg")
    make_image("src/2022-07-04_10-30-00_b.jpg")
    make_image("src/2023-01-01_09-00-00_c.jpg")

    cfg = _config(tmp_path, src)
    with Database(tmp_path / "db.sqlite") as db:
        pipeline = Pipeline(cfg, db)
        result = pipeline.analyze()
        assert len(result.files) == 3
        assert len(result.events) >= 2  # July 2022 vs January 2023
        assert result.plan is not None and len(result.plan) == 3

        exec_result = pipeline.organize(result.plan)
        pipeline.close()

    # All three files copied into the Year/Month/Event structure.
    copied = list((tmp_path / "out").rglob("*.jpg"))
    assert len(copied) == 3
    assert exec_result.copied == 3


def test_stop_aborts_analysis(make_image: Callable[..., Path], tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(20):
        make_image(f"src/2022-07-04_10-{i:02d}-00_{i}.jpg")

    cfg = _config(tmp_path, src)
    with Database(tmp_path / "db.sqlite") as db:
        pipeline = Pipeline(cfg, db)

        def progress(done: int, total: int, message: str) -> None:
            # Request a stop as soon as the first file is reported.
            pipeline.stop()

        result = pipeline.analyze(progress=progress)
        # A requested stop must abort before clustering/planning happen.
        assert result.events == []
        assert result.plan is None
        pipeline.close()


def test_cache_second_run_uses_cache(make_image: Callable[..., Path], tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    make_image("src/2022-07-04_10-00-00_a.jpg")
    cfg = _config(tmp_path, src)
    db_path = tmp_path / "db.sqlite"

    with Database(db_path) as db:
        Pipeline(cfg, db).analyze()

    with Database(db_path) as db:
        result = Pipeline(cfg, db).analyze()
        assert result.progress.cached == 1
        assert result.progress.analyzed == 0
