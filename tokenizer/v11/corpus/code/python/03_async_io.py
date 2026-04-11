import asyncio
from typing import List


async def fetch(url: str) -> str:
    async with client.get(url) as response:
        return await response.text()


async def fetch_all(urls: List[str]) -> List[str]:
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks)


with open("data.json", "r") as f:
    data = f.read()

try:
    parsed = int(data)
except ValueError as e:
    print(f"invalid integer: {e}")
    parsed = 0
finally:
    print("done parsing")
