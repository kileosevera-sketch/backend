"""Manually trigger a full ingestion run from the organization system.

Usage:
    python ingest.py
    python ingest.py --limit 100
"""
import argparse

from app.ingestion.pipeline import run_all


def main():
    parser = argparse.ArgumentParser(description="Run the data ingestion pipeline")
    parser.add_argument("--limit", type=int, default=50, help="records to pull per source")
    args = parser.parse_args()

    print(f"Starting ingestion run (limit={args.limit} per source)...\n")
    results = run_all(args.limit)

    for r in results:
        if "error" in r:
            print(f"  {r['source_type']:18s} FAILED: {r['error']}")
        else:
            print(f"  {r['source_type']:18s} fetched={r['fetched']:<4} inserted={r['inserted']}")

    print("\nIngestion run complete. Check the sync_logs table for the full history.")


if __name__ == "__main__":
    main()
