#!/usr/bin/env python3
import sys
import re
import argparse
import csv
from collections import defaultdict
from statistics import mean

def parse_args():
    parser = argparse.ArgumentParser(description="Parse Gemini OCR logs and generate a metrics summary.")
    parser.add_argument("logfile", nargs="?", type=argparse.FileType("r"), default=sys.stdin,
                        help="Path to log file (or stdin if not specified).")
    parser.add_argument("--csv", type=str, help="Output metrics to a CSV file.")
    return parser.parse_args()

def parse_metrics(line):
    # Expected format:
    # METRICS: file=doc_001.jpg | status=success | attempts=1 | duration=15.4s
    # Optional: ... | reason=Timeout

    if "METRICS:" not in line:
        return None

    try:
        parts = line.split("METRICS:", 1)[1].strip().split("|")
        data = {}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                data[k.strip()] = v.strip()

        # Cleanup/Cast
        if "duration" in data:
            data["duration"] = float(data["duration"].replace("s", ""))
        if "attempts" in data:
            data["attempts"] = int(data["attempts"])

        return data
    except Exception:
        return None

def main():
    args = parse_args()

    total_files = 0
    statuses = defaultdict(int)
    errors = defaultdict(int)
    durations = []
    attempts_list = []

    records = []

    print(f"Reading from {args.logfile.name}...")

    for line in args.logfile:
        m = parse_metrics(line)
        if m:
            total_files += 1
            records.append(m)

            status = m.get("status", "unknown")
            statuses[status] += 1

            if status == "error":
                reason = m.get("reason", "unknown")
                errors[reason] += 1

            if "duration" in m:
                durations.append(m["duration"])
            if "attempts" in m:
                attempts_list.append(m["attempts"])

    if total_files == 0:
        print("No metrics found in input.")
        return

    # Statistics
    avg_duration = mean(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    total_duration = sum(durations)

    # Report
    print("\n--- Gemini OCR Run Summary ---")
    print(f"Total Files Processed: {total_files}")
    print(f"Total Duration (sum):  {total_duration/60:.2f} min")
    print("-" * 30)
    print("Outcomes:")
    for s, count in statuses.items():
        pct = (count / total_files) * 100
        print(f"  {s.upper():<10}: {count:>4} ({pct:.1f}%)")

    if errors:
        print("-" * 30)
        print("Error Reasons:")
        for r, count in errors.items():
            print(f"  {r:<20}: {count}")

    print("-" * 30)
    print("Performance:")
    print(f"  Avg Duration: {avg_duration:.2f}s")
    print(f"  Max Duration: {max_duration:.2f}s")

    if attempts_list:
        retries = sum(1 for a in attempts_list if a > 1)
        print(f"  Files Retried: {retries} ({(retries/total_files)*100:.1f}%)")

    # CSV Export
    if args.csv:
        try:
            with open(args.csv, "w", newline="") as csvfile:
                fieldnames = ["file", "status", "attempts", "duration", "reason"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for r in records:
                    # filtering keys to match fieldnames
                    row = {k: r.get(k, "") for k in fieldnames}
                    writer.writerow(row)
            print(f"\nCSV Report saved to: {args.csv}")
        except OSError as e:
            print(f"\nError writing CSV: {e}")

if __name__ == "__main__":
    main()
