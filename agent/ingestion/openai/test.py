import asyncio
import sys
from pathlib import Path

# Keep this folder first so the local openai.py is imported, then add the
# repo root so app.database can be imported while saving articles.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(1, str(ROOT))

from openai import fetch_openai_news


async def main():

    result = await fetch_openai_news(max_results=10)

    print("Fetched:", result["fetched"])
    print("Saved:", result["saved"])
    print("Duplicates:", result["duplicates_skipped"])

    for article in result["articles"]:
        print("\n-------------------------")
        print("Title:", article["title"])
        print("URL:", article["url"])
        print("Published:", article["published_at"])


asyncio.run(main())
