from __future__ import annotations

import argparse
import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = BASE_DIR / "import" / "movielens"
DEFAULT_OUTPUT_DIR = BASE_DIR / "import"

SCHEMAS = {
    "movies.dat": ["movieId", "title", "genres"],
    "users.dat": ["userId", "gender", "age", "occupation", "zipCode"],
    "ratings.dat": ["userId", "movieId", "rating", "timestamp"],
}


def convert_file(source_file: Path, output_file: Path, header: list[str]) -> int:
    rows_written = 0

    with (
        source_file.open("r", encoding="latin-1", newline="") as source,
        output_file.open("w", encoding="utf-8", newline="") as output,
    ):
        writer = csv.writer(output)
        writer.writerow(header)

        for line_number, line in enumerate(source, start=1):
            line = line.rstrip("\r\n")
            if not line:
                continue

            row = line.split("::")
            if len(row) != len(header):
                raise ValueError(
                    f"{source_file.name}:{line_number}: expected {len(header)} "
                    f"fields, got {len(row)}"
                )

            writer.writerow(row)
            rows_written += 1

    return rows_written


def convert_dataset(source_dir: Path, output_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, header in SCHEMAS.items():
        source_file = source_dir / filename
        output_file = output_dir / filename.replace(".dat", ".csv")

        if not source_file.is_file():
            raise FileNotFoundError(f"Required MovieLens file not found: {source_file}")

        rows_written = convert_file(source_file, output_file, header)
        try:
            display_path = output_file.relative_to(BASE_DIR)
        except ValueError:
            display_path = output_file

        print(f"{display_path}: {rows_written} rows")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert MovieLens 1M .dat files to UTF-8 CSV files."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help=f"Directory with movies.dat, users.dat, ratings.dat "
        f"(default: {DEFAULT_SOURCE_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated CSV files (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert_dataset(args.source_dir.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
