"""Command-line entry point for reproducible historical-data ingestion."""

from __future__ import annotations

import argparse
from pathlib import Path

from football_predictor.ingestion import write_initial_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the initial OpenFootball historical dataset."
    )
    parser.add_argument("--england-root", type=Path, required=True)
    parser.add_argument("--europe-root", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/historical_matches.csv")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/processed/historical_matches.manifest.json")
    )
    args = parser.parse_args()

    manifest = write_initial_dataset(
        england_root=args.england_root,
        europe_root=args.europe_root,
        output_path=args.output,
        manifest_path=args.manifest,
    )
    print(f"Wrote {manifest['total_matches']} matches to {args.output}")


if __name__ == "__main__":
    main()
