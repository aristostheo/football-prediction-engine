"""CLI for chronological comparison of Elo, logistic, Poisson, and ensemble models."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from football_predictor.market import compare_models_to_closing_market, load_market_odds_csv
from football_predictor.models import (
    compare_models_chronologically,
    compare_models_walk_forward,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Elo, logistic, Poisson, and a validation-selected ensemble."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="evaluate the most recent complete seasons with expanding training windows",
    )
    parser.add_argument(
        "--market-odds",
        type=Path,
        nargs="+",
        help=(
            "compare walk-forward forecasts with one or more local CSV odds exports "
            "(canonical columns or Footiqo 1X2 export columns)"
        ),
    )
    args = parser.parse_args()

    features = pd.read_csv(args.input)
    if args.market_odds:
        if not args.walk_forward:
            parser.error("--market-odds requires --walk-forward")
        odds = pd.concat(
            [load_market_odds_csv(path) for path in args.market_odds],
            ignore_index=True,
        )
        comparison = compare_models_to_closing_market(features, odds)
    elif args.walk_forward:
        comparison = compare_models_walk_forward(features)
    else:
        comparison = compare_models_chronologically(features, test_fraction=args.test_fraction)
    print(json.dumps({name: asdict(score) for name, score in comparison.items()}, indent=2))


if __name__ == "__main__":
    main()
