# Anime Downloader

Anime Downloader is an asynchronous script for downloading anime from the https://jut.su/ website. The program allows you to select episodes, resolution, and download mode (synchronous or asynchronous).

## Installation

1. Clone the repository
2. Install the dependencies:
```
pip install -r requirements.txt
```
## Usage
1. Run the script:
```
python main.py
```
2. Enter the link to the anime from the jut.su website. For example:
```
https://jut.su/fullmeetal-alchemist/
```
3. Choose the resolution and episodes to download.

The program will start downloading and display the progress.

## Dependencies
aiofiles: For asynchronous file operations.

aiohttp: For asynchronous HTTP requests.

beautifulsoup4: For HTML parsing.

tqdm: For displaying a progress bar.

## Example

```
Enter the link or name: https://jut.su/fullmeetal-alchemist/
Anime name: fullmeetal-alchemist
Fetched 64 episodes
Choose the resolution:
(1) 360p
(2) 480p
(3) 720p
Your Choice: 3
Enter the episode numbers to download (e.g., 1, 2-5 or . for all): .
Download synchronously? (1)
Download asynchronously (2)
Your Choice: 2
Downloading episodes: 100%|████████████████████| 64/64 [00:30<00:00,  2.12episode/s]
Download complete!!! Time taken: 0m/30s
```



