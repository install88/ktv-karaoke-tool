import os
import shutil
import logging
from pathlib import Path
from typing import Tuple, Optional

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

logger = logging.getLogger(__name__)


class MediaDownloader:
    def __init__(self, temp_folder: str = "./temp"):
        self.temp_folder = Path(temp_folder)
        self.temp_folder.mkdir(parents=True, exist_ok=True)

    def download_media(self, url: str) -> Tuple[str, str]:
        if yt_dlp is None:
            raise ImportError(
                "yt-dlp is not installed. Please install it to download from URLs."
            )

        logger.info(f"Downloading media from URL: {url}")
        
        # yt-dlp 基本設定
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(self.temp_folder / '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }

        # ⭐ 在這裡加上 cookies.txt 支援
        cookies_path = Path("/content/cookies.txt")
        if cookies_path.exists():
            ydl_opts["cookiefile"] = str(cookies_path)
            logger.info(f"Using cookies file: {cookies_path}")
        else:
            logger.warning(
                "cookies.txt not found at /content/cookies.txt, "
                "downloading without cookies (可能會被 YouTube 要求登入 / 驗證)"
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                title = info.get('title', 'download')
                
                logger.info(f"Downloaded: {filename}")
                return filename, title
                
        except Exception as e:
            logger.error(f"Failed to download media: {e}")
            raise

    def copy_local_file(self, file_path: str) -> Tuple[str, str]:
        source_path = Path(file_path)
        
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not source_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        logger.info(f"Copying local file: {file_path}")
        
        dest_path = self.temp_folder / source_path.name
        shutil.copy2(source_path, dest_path)
        
        title = source_path.stem
        
        logger.info(f"Copied to: {dest_path}")
        return str(dest_path), title

    def get_media(self, input_type: str, input_value: str) -> Tuple[str, str]:
        if input_type == "url":
            return self.download_media(input_value)
        elif input_type == "local":
            return self.copy_local_file(input_value)
        else:
            raise ValueError(f"Unknown input type: {input_type}")

    def cleanup(self):
        if self.temp_folder.exists():
            logger.info(f"Cleaning up temp folder: {self.temp_folder}")
            shutil.rmtree(self.temp_folder)
