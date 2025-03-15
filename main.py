import os
import asyncio
import time
import aiofiles
import aiohttp
from typing import List
from aiohttp import TCPConnector, ClientTimeout
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm as atqdm
from tqdm import tqdm as stqdm

# Configuration
LINK = "https://jut.su"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
}
DIR = "anime"
TIMEOUT = ClientTimeout(total=86400)  # Increase the timeout to 24 hours


class Episode:
    def __init__(self, episode_name: str, href: str) -> None:
        self.name = episode_name
        self.href = href
        self.season = href.split("/")[2] if "season" in href else "season-1"


class JutSu:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.connector = TCPConnector(ssl=False)
        self.client = aiohttp.ClientSession(headers=HEADERS, connector=self.connector, timeout=TIMEOUT)

    async def close(self) -> None:
        await self.client.close()

    async def get_all_episodes(self, season: str = None) -> List[Episode]:
        url = f"{LINK}/{self.slug}"
        if season:
            url += f"/{season}"

        main_page = await self.client.get(url)
        soup = BeautifulSoup(await main_page.text(), "html.parser")
        episodes = soup.find_all("a", {"class": "short-btn"})
        return [Episode(episode.text, episode.attrs["href"]) for episode in episodes]

    async def get_download_link(self, href: str, res: str) -> str:
        episode_page = await self.client.get(f"{LINK}/{href}")
        soup = BeautifulSoup(await episode_page.text(), "html.parser")
        source = soup.find("source", {"res": res})
        source = source if source else soup.find("source")
        return source.attrs["src"] if source else None

    async def get_resolution_from_link(self, href: str) -> List[str]:
        episode_page = await self.client.get(f"{LINK}/{href}")
        soup = BeautifulSoup(await episode_page.text(), "html.parser")
        sources = soup.find_all("source")
        resolutions = [source.attrs.get("res", "unknown") for source in sources]
        return resolutions


async def get_link_and_download(inst: JutSu, episode: Episode, res: str, show_percentage: bool = True) -> None:
    cli = inst.client
    link = await inst.get_download_link(episode.href, res)
    if link:
        await download_video(cli, link, f"{DIR}/{inst.slug}/{episode.season}/{episode.name}.mp4",
                            show_percentage=show_percentage)


async def download_video(cli: aiohttp.ClientSession, link: str, path: str, show_percentage: bool = True) -> None:
    if not os.path.exists(path):
        os.makedirs("/".join(path.split("/")[:-1]), exist_ok=True)

    async with cli.get(link) as r:
        total_size = int(r.headers.get('Content-Length', 0))
        downloaded_size = 0

        progress_bar = atqdm if show_percentage else stqdm

        with progress_bar(total=total_size, unit='B', unit_scale=True, desc=path.split("/")[-1]) as pbar:
            async with aiofiles.open(path, "wb+") as f:
                async for d in r.content.iter_any():
                    downloaded_size += len(d)
                    pbar.update(len(d))
                    await f.write(d) if d else None


def print_author_ascii_art():

    author_art = r"""
     _            __     __                    _   
    | |           \ \   / /                   | |  
    | |__  _   _   \ \_/ /   _ _ __   ___  ___| |_ 
    | '_ \| | | |   \   / | | | '_ \ / _ \/ __| __|
    | |_) | |_| |    | || |_| | | | | (_) \__ \ |_ 
    |_.__/ \__, |    |_| \__,_|_| |_|\___/|___/\__|
            __/ |                                  
           |___/        
    """
    print(author_art)


async def async_main(url: str) -> None:
    if url.startswith("http"):
        slug = url.split("/")[3]
        season = url.split("/")[4] if len(url.split("/")) > 4 else None
        print('Anime name:', slug)
    else:
        return print("Enter the correct link!")

    jutsu = JutSu(slug)

    episodes = await jutsu.get_all_episodes(season=season)
    if not episodes:
        return print("No episodes found.")

    available_resolutions = await jutsu.get_resolution_from_link(episodes[0].href)
    available_resolutions = list(set(available_resolutions))
    sorted_available_resolutions = sorted(available_resolutions, key=lambda x: int(x))

    resolution_map = {str(i + 1): res for i, res in enumerate(sorted_available_resolutions)}

    print("Choose the resolution:")
    for key, value in sorted(resolution_map.items(), key=lambda item: int(item[0])):
        print(f"({key}) {value}p")

    res_choice = input("Your Choice: ")

    res = resolution_map.get(res_choice)
    if not res:
        return print("Enter a valid choice!")

    print(f"Fetched {len(episodes)} episodes")

    for idx, episode in enumerate(episodes, start=1):
        print(f"{idx}. {episode.name} - {episode.href}")

    choice = input("Enter the episode numbers to download (e.g., 1, 2-5 or . for all): ")

    selected_episodes = []
    if choice.strip() == ".":
        selected_episodes = episodes
    else:
        for part in choice.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                selected_episodes.extend(episodes[start - 1:end])
            else:
                selected_episodes.append(episodes[int(part) - 1])

    download_type = input("Download synchronously? (1)\nDownload asynchronously (2)\nYour Choice: ")

    start_time = time.time()

    if download_type == "1":
        # Download synchronously
        for episode in selected_episodes:
            await get_link_and_download(jutsu, episode, res)
    elif download_type == "2":
        # Limit the number of concurrent downloads to 5
        semaphore = asyncio.Semaphore(5)

        async def limited_download(episode):
            async with semaphore:
                await get_link_and_download(jutsu, episode, res, False)

        # Download asynchronously with a limit of 5 concurrent downloads
        tasks = [limited_download(episode) for episode in selected_episodes]
        for f in atqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading episodes", unit="episode"):
            await f
    else:
        print("Invalid choice. Please enter '1' for synchronous or '2' for asynchronous downloading.")

    end_time = time.time()
    elapsed_time = end_time - start_time

    await jutsu.close()

    if elapsed_time > 3600:
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        print(f'Download complete!!! Time taken: {hours}h/{minutes}m/{seconds}s')
    elif elapsed_time > 60:
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        print(f'Download complete!!! Time taken: {minutes}m/{seconds}s')
    else:
        print(f'Download complete!!! Time taken: {elapsed_time:.2f}s')


def sync_main(url: str) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_main(url))


if __name__ == "__main__":
    user_input = input("Enter the link or name: ")
    sync_main(user_input)
    print('Finish!!!')
    print_author_ascii_art()