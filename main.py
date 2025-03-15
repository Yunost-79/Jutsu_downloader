import os
import asyncio
import time
import aiofiles
import aiohttp
import re
from typing import List, Optional
from aiohttp import TCPConnector, ClientTimeout
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm as atqdm
from tqdm import tqdm as stqdm

LINK = "https://jut.su"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
    "Referer": "https://jut.su/",
}
DIR = "anime"
TIMEOUT = ClientTimeout(total=86400)

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

    async def get_download_link(self, href: str, res: str) -> Optional[str]:
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

    async def get_anime_name(self) -> str:
        url = f"{LINK}/{self.slug}"
        main_page = await self.client.get(url)
        soup = BeautifulSoup(await main_page.text(), "html.parser")
        title_container = soup.find('h1', {'class': 'header video allanimevideo anime_padding_for_title'})
        if title_container:
            primal_title_name = title_container.get_text(strip=True)
            final_title_name = re.sub(r"Смотреть | все серии и сезоны", "", primal_title_name)
            return final_title_name
        return self.slug



class AnimeDownloader:
    def __init__(self) -> None:
        self.jutsu: Optional[JutSu] = None

    async def download_video(self, cli: aiohttp.ClientSession, link: str, path: str, show_percentage: bool = True) -> None:
        try:
            if not os.path.exists(path):
                os.makedirs("/".join(path.split("/")[:-1]), exist_ok=True)
            async with cli.get(link) as r:
                if r.status != 200:
                    print(f"Failed to download {path}. Status code: {r.status}")
                    return
                content_type = r.headers.get("Content-Type", "")
                if "video/mp4" not in content_type:
                    print(f"Unexpected content type: {content_type}. Expected video/mp4.")
                    return
                total_size = int(r.headers.get('Content-Length', 0))
                downloaded_size = 0
                progress_bar = atqdm if show_percentage else stqdm
                with progress_bar(total=total_size, unit='B', unit_scale=True, desc=path.split("/")[-1]) as pbar:
                    async with aiofiles.open(path, "wb+") as f:
                        async for d in r.content.iter_any():
                            downloaded_size += len(d)
                            pbar.update(len(d))
                            await f.write(d) if d else None
        except Exception as e:
            print(f"Error downloading {path}: {e}")
 
    @staticmethod   
    def sanitize_filename(filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "_", filename)

    async def get_link_and_download(self, episode: Episode, res: str, show_percentage: bool = True) -> None:

        if not self.jutsu:
            raise ValueError("JutSu instance not initialized")
        link = await self.jutsu.get_download_link(episode.href, res)
        if link:
            sanitized_name = self.sanitize_filename(episode.name)
            await self.download_video(self.jutsu.client, link, f"{DIR}/{self.jutsu.slug}/{episode.season}/{sanitized_name}.mp4", show_percentage)
    
    @staticmethod
    def print_author_ascii_art() -> None:
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

    async def async_main(self, url: str) -> None:
        while True:
            try:
                slug, season = self.parse_url(url)
                self.jutsu = JutSu(slug)
                anime_name = await self.jutsu.get_anime_name()
                print(f'Anime name: {slug} / {anime_name}')
                episodes = await self.jutsu.get_all_episodes(season=season)
                if not episodes:
                    print("No episodes found.")
                    continue
                resolution_map = await self.choose_resolution(episodes[0].href)
                res = self.get_resolution_choice(resolution_map)
                selected_episodes = self.select_episodes(episodes)
                download_type = self.choose_download_type()
                start_time = time.time()
                await self.download_episodes(selected_episodes, res, download_type)
                self.print_download_time(start_time)
                self.print_author_ascii_art()
                break
            except ValueError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
            finally:
                if self.jutsu:
                    await self.jutsu.close()

    def parse_url(self, url: str) -> tuple[str, Optional[str]]:
        parts = url.split("/")
        if len(parts) < 4:
            raise ValueError("Invalid URL format")
        slug = parts[3]
        season = parts[4] if len(parts) > 4 else None
        return slug, season

    async def choose_resolution(self, episode_href: str) -> dict[str, str]:
        available_resolutions = await self.jutsu.get_resolution_from_link(episode_href)
        available_resolutions = list(set(available_resolutions))
        sorted_available_resolutions = sorted(available_resolutions, key=lambda x: int(x))
        return {str(i + 1): res for i, res in enumerate(sorted_available_resolutions)}

    def get_resolution_choice(self, resolution_map: dict[str, str]) -> str:
        print("Choose the resolution:")
        for key, value in sorted(resolution_map.items(), key=lambda item: int(item[0])):
            print(f"({key}) {value}p")
        while True:
            res_choice = input("Your Choice: ")
            res = resolution_map.get(res_choice)
            if res:
                return res
            print("Invalid choice. Please try again.")

    def select_episodes(self, episodes: List[Episode]) -> List[Episode]:
        print(f"Fetched {len(episodes)} episodes")
        for idx, episode in enumerate(episodes, start=1):
            print(f"{idx}. {episode.name} - {episode.href}")
        while True:
            choice = input("Enter the episode numbers to download (e.g., 1, 2-5, 10-, or . for all): ")
            selected_episodes = []
            if choice.strip() == ".":
                return episodes
            try:
                for part in choice.split(","):
                    part = part.strip()
                    if "-" in part:
                        start_end = part.split("-")
                        if len(start_end) == 2:
                            start = start_end[0].strip()
                            end = start_end[1].strip()
                            if end == "":
                                start = int(start)
                                if 1 <= start <= len(episodes):
                                    selected_episodes.extend(episodes[start - 1:])
                                else:
                                    print(f"Invalid start number: {start}. Please try again.")
                                    break
                            else:
                                start = int(start)
                                end = int(end)
                                if 1 <= start <= len(episodes) and 1 <= end <= len(episodes) and start <= end:
                                    selected_episodes.extend(episodes[start - 1:end])
                                else:
                                    print(f"Invalid range: {part}. Please try again.")
                                    break
                        else:
                            print(f"Invalid range format: {part}. Please try again.")
                            break
                    else:
                        if part.isdigit():
                            episode_num = int(part)
                            if 1 <= episode_num <= len(episodes):
                                selected_episodes.append(episodes[episode_num - 1])
                            else:
                                print(f"Invalid episode number: {episode_num}. Please try again.")
                                break
                        else:
                            print(f"Invalid input: {part}. Please enter numbers or ranges.")
                            break
                else:
                    return selected_episodes
            except ValueError:
                print("Invalid input. Please enter numbers or ranges.")

    def choose_download_type(self) -> str:
        while True:
            download_type = input("Download synchronously? (1)\nDownload asynchronously (2)\nYour Choice: ")
            if download_type in {"1", "2"}:
                return download_type
            print("Invalid choice. Please enter '1' for synchronous or '2' for asynchronous downloading.")

    async def download_episodes(self, episodes: List[Episode], res: str, download_type: str) -> None:
        if download_type == "1":
            for episode in episodes:
                await self.get_link_and_download(episode, res)
        elif download_type == "2":
            num_threads = self.get_num_threads()
            semaphore = asyncio.Semaphore(num_threads)
            async def limited_download(episode):
                async with semaphore:
                    await self.get_link_and_download(episode, res, False)
            tasks = [limited_download(episode) for episode in episodes]
            for f in atqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading episodes", unit="episode"):
                await f

    def get_num_threads(self) -> int:
        while True:
            try:
                num_threads = int(input("Enter the number of concurrent downloads (1-20): "))
                if 1 <= num_threads <= 20:
                    return num_threads
                print("Please enter a number between 1 and 20.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def print_download_time(self, start_time: float) -> None:
        end_time = time.time()
        elapsed_time = end_time - start_time
        if elapsed_time > 3600:
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)
            print(f'Download complete!!! Time taken: {hours} hours {minutes} minutes {seconds} seconds')
        elif elapsed_time > 60:
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            print(f'Download complete!!! Time taken: {minutes} minutes {seconds} seconds')
        else:
            print(f'Download complete!!! Time taken: {elapsed_time:.2f} seconds')

def main() -> None:
    downloader = AnimeDownloader()
    while True:
        user_input = input("Enter the link or name: ")
        if user_input != "":
            if user_input.startswith("http"):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(downloader.async_main(user_input))
            else:
                print("Invalid link. Links must start with 'http'. Please try again!")
        else:
            print("Input cannot be empty. Please try again!")

if __name__ == "__main__":
    main()