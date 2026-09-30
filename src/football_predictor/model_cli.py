"""CLI for chronological comparison of Elo, logistic, Poisson, and ensemble models."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from football_predictor.models import compare_models_chronologically


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Elo, logistic, Poisson, and a validation-selected ensemble."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    comparison = compare_models_chronologically(
        pd.read_csv(args.input), test_fraction=args.test_fraction
    )
    print(json.dumps({name: asdict(score) for name, score in comparison.items()}, indent=2))


if __name__ == "__main__":
    main()
