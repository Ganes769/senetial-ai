import asyncio
import sys
from pathlib import Path

# Running this file from agent/ingestion puts that folder on sys.path,
# not the repo root where the app package lives.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arxiv import fetch_recent_papers


async def main():

    result = await fetch_recent_papers(max_results=10)

    print("Fetched:", result["fetched"])
    print("Saved:", result["saved"])
    print("Duplicates:", result["duplicates_skipped"])

    for paper in result["papers"]:
        print("\n-------------------------")
        print("Title:", paper["title"])
        print("URL:", paper["url"])


asyncio.run(main())