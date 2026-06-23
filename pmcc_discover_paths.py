#!/usr/bin/env python3
"""Discover recurring TSLA spot patterns to inform PMCC scenario paths."""

from __future__ import annotations

import argparse

from pmcc.discover_paths import discover_tsla_patterns, format_discovery


def main() -> None:
    ap = argparse.ArgumentParser(description="TSLA historical pattern discovery for PMCC paths")
    ap.add_argument("--period", default="10y")
    args = ap.parse_args()

    df = discover_tsla_patterns(period=args.period)
    print(format_discovery(df))
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()