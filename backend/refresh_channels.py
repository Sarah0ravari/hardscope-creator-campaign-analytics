import os
import sys

from app import ingest_channel


def main():
    channel_ids = [item.strip() for item in os.getenv("YT_CHANNEL_IDS", "").split(",") if item.strip()]
    campaign_label = os.getenv("YT_CAMPAIGN_LABEL")
    max_results = int(os.getenv("YT_MAX_RESULTS", "15"))

    if not channel_ids:
        print("Set YT_CHANNEL_IDS to a comma-separated list of YouTube channel IDs.", file=sys.stderr)
        return 1

    for channel_id in channel_ids:
        try:
            result = ingest_channel(
                channel_id=channel_id,
                campaign_label=campaign_label,
                max_results=max_results,
            )
            print(
                f"{result['creator_name']}: fetched={result['fetched']} inserted={result['inserted']} updated={result['updated']}"
            )
        except Exception as exc:
            print(f"{channel_id}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
