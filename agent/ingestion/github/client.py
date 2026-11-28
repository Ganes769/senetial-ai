import os
import httpx
from dotenv import load_dotenv
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_API = "https://api.github.com"

class GitHubClient:

    def __init__(self):

        if not GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is missing")

        self.headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def get(self, endpoint: str, params=None):

        async with httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=self.headers,
            timeout=30
        ) as client:

            response = await client.get(
                endpoint,
                params=params
            )

            response.raise_for_status()

            return response.json()
