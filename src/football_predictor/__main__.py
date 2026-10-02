"""Command-line entry point for reproducible historical-data ingestion."""

from __future__ import annotations

import argparse
from pathlib import Path

from football_predictor.ingestion import refresh_openfootball_dataset, write_initial_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build or safely refresh the OpenFootball historical dataset."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="download the latest OpenFootball files and safely refresh the model dataset",
    )
    parser.add_argument("--england-root", type=Path)
    parser.add_argument("--europe-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--allow-removed-matches",
        action="store_true",
        help="accept upstream removals after reviewing the source change (refresh only)",
    )
    args = parser.parse_args()

    if args.refresh:
        if args.england_root or args.europe_root:
            parser.error("--refresh cannot be combined with local source roots")
        manifest = refresh_openfootball_dataset(
            output_path=args.output or Path("data/model/historical_matches.csv.gz"),
            manifest_path=args.manifest
            or Path("data/model/historical_matches.manifest.json"),
            allow_removed_matches=args.allow_removed_matches,
        )
        print(
            f"Refreshed {manifest['total_matches']} matches: "
            f"{manifest['added_matches']} added, "
            f"{manifest['corrected_scores']} corrected, "
            f"{manifest['removed_matches']} removed"
        )
        return

    if args.allow_removed_matches:
        parser.error("--allow-removed-matches requires --refresh")
    if args.england_root is None or args.europe_root is None:
        parser.error("provide --refresh or both --england-root and --europe-root")
    output_path = args.output or Path("data/processed/historical_matches.csv")
    manifest_path = args.manifest or Path("data/processed/historical_matches.manifest.json")
    manifest = write_initial_dataset(
        england_root=args.england_root,
        europe_root=args.europe_root,
        output_path=output_path,
        manifest_path=manifest_path,
    )
    print(f"Wrote {manifest['total_matches']} matches to {output_path}")


if __name__ == "__main__":
    main()
