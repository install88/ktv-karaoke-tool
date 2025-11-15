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
    print("Select input type:")
    print("  1) YouTube URL")
    print("  2) Local file path")
    
    while True:
        choice = input("\nEnter choice (1 or 2): ").strip()
        if choice in ['1', '2']:
            break
        print("Invalid choice. Please enter 1 or 2.")
    
    input_type = "url" if choice == '1' else "local"
    
    if input_type == "url":
        input_value = input("\nEnter YouTube URL: ").strip()
    else:
        input_value = input("\nEnter local file path: ").strip()
    
    print("\nSelect output format:")
    print("  1) MP3 (audio only)")
    print("  2) MP4 (video)")
    
    while True:
        format_choice = input("\nEnter choice (1 or 2): ").strip()
        if format_choice in ['1', '2']:
            break
        print("Invalid choice. Please enter 1 or 2.")
    
    output_format = "mp3" if format_choice == '1' else "mp4"
    
    output_folder = input("\nEnter output folder (press Enter for default './output'): ").strip()
    if not output_folder:
        output_folder = "./output"
    
    print("\n" + "-"*60)
    print("Summary:")
    print(f"  Input type: {input_type}")
    print(f"  Input: {input_value}")
    print(f"  Output format: {output_format}")
    print(f"  Output folder: {output_folder}")
    print("-"*60 + "\n")
    
    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled.")
        sys.exit(0)
    
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
            language=config['speech_to_text']['language'] if config['speech_to_text']['language'] != 'auto' else None
        )
        print(f"  ✓ Subtitles generated")
        
        print("[7/7] Creating final files and saving to output folder...")
        logger.info("Step 7: Creating final output files")
        
        if output_format == "mp3":
            final_output = output_path / f"{title}_ktv.mp3"
            processor.convert_to_mp3(str(ktv_mix_file), str(final_output))
        else:
            final_output = output_path / f"{title}_ktv.mp4"
            processor.create_video_with_audio(
                media_file if input_type == "url" or Path(input_value).suffix in ['.mp4', '.avi', '.mkv'] else None,
                str(ktv_mix_file),
                str(final_output)
            )
        
        print(f"  ✓ Final file created")
        
        if not config.get('keep_temp_files', False):
            logger.info("Cleaning up temporary files")
            downloader.cleanup()
        
        print("\n" + "="*60)
        print("  Processing Complete!")
        print("="*60)
        print(f"\nOutput folder: {output_path.absolute()}")
        print(f"Audio/Video file: {final_output.name}")
        for subtitle_file in subtitle_files:
            print(f"Subtitle file: {Path(subtitle_file).name}")
        
        print("\nKTV Audio Channel Layout:")
        print("  LEFT channel: Instrumental only (karaoke mode)")
        print("  RIGHT channel: Full vocal + instrumental (original song)")
        print("\nTip: Use a media player's balance control to switch between modes!")
        print("="*60 + "\n")
        
        logger.info("KTV conversion completed successfully")
        
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
