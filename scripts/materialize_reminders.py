import asyncio
import sys

from app.workers.reminder_materializer import run_reminder_materializer


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    results = await run_reminder_materializer(limit=limit)
    print(f"processed_requests={len(results)}")
    for result in results:
        print(
            f"request_id={result.request_id} status={result.status} "
            f"created={result.created_count} existing={result.existing_count} suppressed={result.suppressed_count}"
        )


if __name__ == "__main__":
    asyncio.run(main())
