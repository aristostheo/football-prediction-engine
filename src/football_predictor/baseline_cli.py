"""CLI for evaluating the fixed Elo probability baseline chronologically."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from football_predictor.evaluation import (
    add_elo_probabilities,
    chronological_holdout,
    evaluate_probabilities,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the Elo baseline on a chronological holdout."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    probabilities = add_elo_probabilities(pd.read_csv(args.input))
    holdout = chronological_holdout(probabilities, test_fraction=args.test_fraction)
    metrics = {
        competition: asdict(evaluate_probabilities(matches))
        for competition, matches in holdout.groupby("competition", sort=True)
    }
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
