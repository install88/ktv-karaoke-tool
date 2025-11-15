#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path

def check_ffmpeg():
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        print("✓ FFmpeg is installed")
        version_line = result.stdout.split('\n')[0]
        print(f"  Version: {version_line}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ FFmpeg not found")
        return False

def check_python_packages():
    packages = {
        'yt_dlp': 'yt-dlp',
        'pydub': 'pydub',
        'numpy': 'numpy',
    }
    
    missing = []
    for module, name in packages.items():
        try:
            __import__(module)
            print(f"✓ {name} is installed")
        except ImportError:
            print(f"✗ {name} is not installed")
            missing.append(name)
    
    return len(missing) == 0

def check_project_structure():
    required_files = [
        'main.py',
        'downloader.py',
        'audio_processing.py',
        'subtitles.py',
        'config.json',
        'requirements.txt',
        'README.md'
    ]
    
    all_exist = True
    for file in required_files:
        if Path(file).exists():
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 60)
    print("KTV Converter - System Check")
    print("=" * 60)
    print()
    
    print("Checking FFmpeg...")
    ffmpeg_ok = check_ffmpeg()
    print()
    
    print("Checking Python packages (basic)...")
    packages_ok = check_python_packages()
    print()
    
    print("Checking project structure...")
    structure_ok = check_project_structure()
    print()
    
    print("=" * 60)
    if ffmpeg_ok and packages_ok and structure_ok:
        print("✓ Basic system check passed!")
        print()
        print("Note: Heavy AI packages (demucs, whisper) require")
        print("significant disk space and are best installed locally.")
        print()
        print("To run the full application locally:")
        print("  1. Install all requirements: pip install -r requirements.txt")
        print("  2. Run: python main.py")
    else:
        print("✗ Some components are missing")
        print("See README.md for installation instructions")
    print("=" * 60)

if __name__ == "__main__":
    main()
