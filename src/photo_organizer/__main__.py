"""Command-line interface for PhotoOrganizer AI.

Provides a headless workflow (scan -> analyse -> preview -> confirm -> organise)
that mirrors what the GUI offers, plus a ``resume`` command. Run with::

    python -m photo_organizer --config config.yaml
    python -m photo_organizer --config config.yaml --yes      # skip confirmation
    python -m photo_organizer --config config.yaml resume
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from .config import Config, ConfigError
from .database import Database
from .logging_setup import configure_logging, get_logger
from .organizer.planner import OrganizePlan
from .pipeline import Pipeline, PipelineResult

_LOG = get_logger("cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-organizer",
        description="Locally, AI-assisted organisation of photos and videos.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to the YAML/JSON configuration file.",
    )
    parser.add_argument("--source", type=Path, help="Override the source directory.")
    parser.add_argument("--target", type=Path, help="Override the target directory.")
    parser.add_argument(
        "--operation", choices=["move", "copy"], help="Override move/copy operation."
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not ask for confirmation before moving/copying.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse and print the plan without touching any files.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["organize", "resume"],
        default="organize",
        help="What to do (default: organize).",
    )
    return parser


def _print_preview(plan: OrganizePlan) -> None:
    tree = plan.target_root_tree()
    print("\nPreview of the target structure:")
    for year in sorted(tree):
        print(f"  {year}/")
        for month in sorted(tree[year]):
            print(f"    {month}/")
            for event, count in sorted(tree[year][month].items()):
                print(f"      {event}/  ({count} files)")
    print(f"\nTotal: {len(plan)} files.\n")


def _load_config(args: argparse.Namespace) -> Config:
    config = Config.load(args.config)
    if args.source:
        config.source_dir = args.source
    if args.target:
        config.target_dir = args.target
    if args.operation:
        from .config import Operation

        config.operation = Operation(args.operation)
    return config


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        config = _load_config(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(config.logging)

    with Database(config.database_path) as db:
        pipeline = Pipeline(config, db)
        try:
            if args.command == "resume":
                _LOG.info("Resuming previous run ...")
                bar = tqdm(total=0, desc="Resuming", unit="file")

                def _resume_progress(done: int, total: int, _msg: str) -> None:
                    bar.total = total
                    bar.n = done
                    bar.refresh()

                pipeline.resume_organize(progress=_resume_progress)
                bar.close()
                return 0

            result = _run_analysis(pipeline)
            if result.plan is None or len(result.plan) == 0:
                print("No media files found to organise.")
                return 0
            _print_preview(result.plan)

            if args.dry_run:
                print("Dry-run: no files were moved or copied.")
                return 0

            if not args.yes and not _confirm(config):
                print("Aborted; no files were changed.")
                return 0

            _run_organize(pipeline, result.plan)
        finally:
            pipeline.close()
    return 0


def _run_analysis(pipeline: Pipeline) -> PipelineResult:
    bar = tqdm(total=0, desc="Analysing", unit="file")

    def _progress(done: int, total: int, _msg: str) -> None:
        bar.total = total
        bar.n = done
        bar.refresh()

    result = pipeline.analyze(progress=_progress)
    bar.close()
    print(
        f"Analysed {result.progress.analyzed} files "
        f"({result.progress.cached} from cache, {result.progress.failed} failed); "
        f"found {len(result.events)} events."
    )
    return result


def _run_organize(pipeline: Pipeline, plan: OrganizePlan) -> None:
    bar = tqdm(total=len(plan), desc="Organising", unit="file")

    def _progress(done: int, total: int, _msg: str) -> None:
        bar.total = total
        bar.n = done
        bar.refresh()

    pipeline.organize(plan, progress=_progress)
    bar.close()


def _confirm(config: Config) -> bool:
    verb = "move" if config.operation.value == "move" else "copy"
    answer = input(f"Proceed to {verb} the files into {config.target_dir}? [y/N] ")
    return answer.strip().lower() in {"y", "yes", "j", "ja"}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
