import csv
import sys
from pathlib import Path


USAGE = """Clean a leads.csv file by keeping only rows where cleaned_phone is a 10-digit number.

Usage:
    python clean_leads_csv.py /path/to/leads.csv [--inplace]

The cleaned file is written to <original_name>_clean.csv unless --inplace is passed, in which case the original file is overwritten.
"""


def is_valid_phone(value: str) -> bool:
    """Return True if the string is exactly 10 digits."""
    return value.isdigit() and len(value) == 10


def clean_file(path: Path, inplace: bool = False) -> Path:
    output_path = path if inplace else path.with_name(path.stem + "_clean.csv")

    with path.open(newline="", encoding="utf-8") as infile, output_path.open("w", newline="", encoding="utf-8") as outfile:
        reader = csv.DictReader(infile)
        if "cleaned_phone" not in reader.fieldnames:
            raise SystemExit("Input CSV must contain a 'cleaned_phone' column")

        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()

        kept, skipped = 0, 0
        for row in reader:
            phone = row.get("cleaned_phone", "").strip()
            if is_valid_phone(phone):
                writer.writerow(row)
                kept += 1
            else:
                skipped += 1

    print(f"Wrote {kept} valid rows to {output_path} (skipped {skipped} invalid rows)")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(USAGE)
        sys.exit(0)

    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)

    inplace_flag = "--inplace" in sys.argv[2:]
    clean_file(target, inplace=inplace_flag) 