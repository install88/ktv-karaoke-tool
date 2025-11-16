#!/usr/bin/env python3

import os
import sys
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from downloader import MediaDownloader
from audio_processing import AudioProcessor
from subtitles import SubtitleGenerator
from urllib.parse import urlparse, parse_qs


def clean_youtube_url(raw_url: str) -> str:
    """
    把各種長長的 YouTube 連結（含 list=、start_radio= 等）縮成
    https://www.youtube.com/watch?v=VIDEO_ID 的標準型式。
    如果不是 YouTube，就原樣回傳。
    """
    raw_url = raw_url.strip()
    if not raw_url:
        raise ValueError("YouTube URL 不可為空")

    # 先處理 youtu.be 短網址，例如:
    # https://youtu.be/KWymGqoI2FU?list=xxx
    if "youtu.be/" in raw_url:
        video_id = raw_url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={video_id}"

    parsed = urlparse(raw_url)

    # 如果 domain 不是 YouTube，就不要亂動，直接回傳
    if "youtube.com" not in parsed.netloc and "youtu.be" not in parsed.netloc:
        return raw_url

    qs = parse_qs(parsed.query)
    video_id = qs.get("v", [None])[0]

    if not video_id:
        # 找不到 v 參數，就原樣回傳（避免弄壞一些奇怪格式）
        return raw_url

    # 統一轉成乾淨版：
    # https://www.youtube.com/watch?v=VIDEO_ID
    return f"https://www.youtube.com/watch?v={video_id}"


def setup_logging(log_folder: str = "./logs", log_level: str = "INFO") -> None:
    log_path = Path(log_folder)
    log_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"ktv_converter_{timestamp}.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")


def load_config(config_file: str = "config.json") -> dict:
    if Path(config_file).exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {
            "default_output_folder": "./output",
            "temp_folder": "./temp",
            "keep_temp_files": False,
            "vocal_separation": {"method": "demucs", "model": "htdemucs"},
            "speech_to_text": {"model": "base", "language": "auto"},
            "subtitle_format": "ass",
            "logging": {"log_folder": "./logs", "log_level": "INFO"}
        }


def print_banner():
    print("\n" + "="*60)
    print("  KTV Converter - YouTube/Local File to Karaoke")
    print("="*60 + "\n")


def get_user_input():
    # 目前只支援 YouTube URL，自動清洗成乾淨的 watch?v=xxx
    input_type = "url"
    
    if input_type == "url":
        raw_url = input("\nEnter YouTube URL: ").strip()
        input_value = clean_youtube_url(raw_url)
    else:
        input_value = input("\nEnter local file path: ").strip()
    
    # 輸出格式固定 MP4
    output_format = "mp4"
    # 輸出資料夾固定 ./output
    output_folder = "./output"
    
    print("\n" + "-"*60)
    print("Summary:")
    print(f"  Input type: {input_type}")
    print(f"  Input: {input_value}")
    print(f"  Output format: {output_format}")
    print(f"  Output folder: {output_folder}")
    print("-"*60 + "\n")
    
    return input_type, input_value, output_format, output_folder


def main():
    logger = logging.getLogger(__name__)
    
    try:
        print_banner()
        
        config = load_config()
        setup_logging(
            config['logging']['log_folder'],
            config['logging']['log_level']
        )
        
        logger.info("KTV Converter started")
        
        input_type, input_value, output_format, output_folder = get_user_input()
        
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        
        temp_folder = config['temp_folder']
        Path(temp_folder).mkdir(parents=True, exist_ok=True)
        
        print("\n[1/7] Validating input...")
        logger.info("Step 1: Validating input")
        
        downloader = MediaDownloader(temp_folder)
        
        print("[2/7] Downloading or copying media...")
        logger.info("Step 2: Getting media")
        media_file, title = downloader.get_media(input_type, input_value)
        print(f"  ✓ Media ready: {Path(media_file).name}")
        
        processor = AudioProcessor(temp_folder)
        
        print("[3/7] Extracting audio...")
        logger.info("Step 3: Extracting audio")
        audio_file = processor.extract_audio(media_file)
        print(f"  ✓ Audio extracted")
        
        print("[4/7] Separating vocals (this may take a few minutes)...")
        logger.info("Step 4: Separating vocals")
        vocals_file, instrumental_file = processor.separate_vocals(
            audio_file,
            model=config['vocal_separation']['model']
        )
        print(f"  ✓ Vocals separated")
        
        print("[5/7] Creating KTV stereo mix...")
        logger.info("Step 5: Creating KTV stereo mix")
        ktv_mix_file = Path(temp_folder) / f"{title}_ktv_mix.wav"
        processor.create_ktv_stereo_mix(
            vocals_file,
            instrumental_file,
            str(ktv_mix_file)
        )
        print(f"  ✓ KTV stereo mix created")
        
        print("[6/7] Transcribing lyrics and generating subtitles (this may take a few minutes)...")
        logger.info("Step 6: Generating subtitles")
        subtitle_gen = SubtitleGenerator(
            model_size=config['speech_to_text']['model']
        )
        
        subtitle_base = output_path / f"{title}_ktv"
        subtitle_files = subtitle_gen.generate_subtitles(
            str(vocals_file),
            str(subtitle_base),
            format_type=config['subtitle_format'],
            language=(
                config['speech_to_text']['language']
                if config['speech_to_text']['language'] != 'auto'
                else None
            )
        )
        print(f"  ✓ Subtitles generated")
        
        print("[7/7] Creating final MP4 (KTV audio, no burned subtitles)...")
        logger.info("Step 7: Creating final MP4 (audio only, no burned subtitles)")
        
        try:
            if output_format == "mp3":
                # 理論上現在不會走這裡，但保留一下
                final_output = output_path / f"{title}_ktv.mp3"
                processor.convert_to_mp3(str(ktv_mix_file), str(final_output))
            else:
                final_output = output_path / f"{title}_ktv.mp4"

                # 1) 判斷有沒有原始 MV 可以拿來當畫面
                video_source = None
                if input_type == "url" or (
                    input_type == "local"
                    and Path(input_value).suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov', '.flv']
                ):
                    video_source = media_file
                    if not Path(video_source).exists():
                        logger.warning(f"Video source file not found: {video_source}")
                        video_source = None

                # 2) 只把新 KTV 音軌塞回影片，不燒字幕
                processor.create_video_with_audio(
                    video_source,
                    str(ktv_mix_file),
                    str(final_output),
                )
            
            print(f"  ✓ Final MP4 created")
            
        except Exception as e:
            logger.error(f"Error creating final output: {e}")
            raise
        finally:
            if not config.get('keep_temp_files', False):
                logger.info("Cleaning up temporary files (you can comment this out if you want to keep temp)")
                # 你如果希望永遠保留 temp，就把下面兩行打開 / 關掉依需求
                # try:
                #     downloader.cleanup()
                # except Exception as cleanup_error:
                #     logger.warning(f"Error during cleanup: {cleanup_error}")
        
        print("\n" + "="*60)
        print("  Processing Complete!  (Steps 1–7 done, no MPG/DVD)")
        print("="*60)
        print(f"\nOutput folder: {output_path.absolute()}")
        print(f"KTV MP4 file: {final_output.name}")
        for subtitle_file in subtitle_files:
            print(f"Subtitle file: {Path(subtitle_file).name}")
        
        print("\nKTV Audio Channel Layout:")
        print("  LEFT channel: Instrumental only (karaoke mode)")
        print("  RIGHT channel: Full vocal + instrumental (original song)")
        print("\nTip: Use a media player's balance control to switch between modes!")
        print("="*60 + "\n")
        
        logger.info("KTV conversion completed successfully (up to step 7)")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        logger.exception("An error occurred during processing")
        sys.exit(1)


if __name__ == "__main__":
    main()
