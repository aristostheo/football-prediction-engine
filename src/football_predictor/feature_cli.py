"""CLI for turning canonical historical matches into model-ready feature rows."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from football_predictor.features import build_pre_match_features


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-safe pre-match features.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/historical_match_features.csv")
    )
    args = parser.parse_args()

    features = build_pre_match_features(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output, index=False)
    print(f"Wrote {len(features)} feature rows to {args.output}")


if __name__ == "__main__":
    main()
