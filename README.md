# KTV Converter

A Python application that converts YouTube videos or local media files into karaoke-style (KTV) files with synchronized subtitles.

## Project Overview

This tool processes video or audio files to create:
- **KTV-style stereo audio** with special channel layout:
  - **LEFT channel**: Instrumental only (karaoke mode with reduced/no vocals)
  - **RIGHT channel**: Full vocal + instrumental (original song)
- **Synchronized subtitles** (.ass or .srt format) with timing that follows the actual singing
- Output in either MP3 (audio) or MP4 (video) format

### How It Works

1. Download from YouTube URL or use a local media file
2. Extract audio track
3. Separate vocals from instrumental using AI-powered vocal separation (Demucs)
4. Create KTV stereo mix (LEFT=instrumental, RIGHT=full)
5. Transcribe lyrics with precise timestamps using OpenAI Whisper
6. Generate karaoke-style subtitles with word-by-word timing
7. Export final MP3/MP4 + subtitle files

## Dependencies

### System Requirements

- **Python**: 3.8 or higher (tested with 3.11)
- **FFmpeg**: Required for audio/video processing

### Python Libraries

All Python dependencies are listed in `requirements.txt`:
- `yt-dlp` - YouTube video downloading
- `openai-whisper` - Speech-to-text transcription
- `demucs` - AI-powered vocal separation
- `pydub` - Audio manipulation
- `numpy` - Numerical operations
- `pyinstaller` - For packaging into executable

## Installation

### On Replit

1. The project will automatically install Python dependencies when you run it
2. FFmpeg is pre-installed in the Replit environment
3. Simply click "Run" or execute:
   ```bash
   python main.py
   ```

### Running Locally

#### 1. Install FFmpeg

**Windows:**
- Download from https://ffmpeg.org/download.html
- Add to PATH environment variable

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

#### 2. Set Up Python Environment

```bash
# Clone or download this project
cd ktv-converter

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Run the Application

```bash
python main.py
```

## Usage

When you run the application, you'll be prompted for:

1. **Input type**: Choose between YouTube URL or local file path
2. **Input value**: Provide the URL or file path
3. **Output format**: Choose MP3 (audio only) or MP4 (video)
4. **Output folder**: Specify where to save files (default: `./output`)

### Example Session

```
Select input type:
  1) YouTube URL
  2) Local file path

Enter choice (1 or 2): 2

Enter local file path: /path/to/song.mp4

Select output format:
  1) MP3 (audio only)
  2) MP4 (video)

Enter choice (1 or 2): 1

Enter output folder (press Enter for default './output'): 

Summary:
  Input type: local
  Input: /path/to/song.mp4
  Output format: mp3
  Output folder: ./output

Proceed? (y/n): y

[1/7] Validating input...
[2/7] Downloading or copying media...
[3/7] Extracting audio...
[4/7] Separating vocals (this may take a few minutes)...
[5/7] Creating KTV stereo mix...
[6/7] Transcribing lyrics and generating subtitles...
[7/7] Creating final files and saving to output folder...

Processing Complete!

Output folder: /absolute/path/to/output
Audio/Video file: song_ktv.mp3
Subtitle file: song_ktv.ass
```

## Configuration

Edit `config.json` to customize default settings:

```json
{
  "default_output_folder": "./output",
  "temp_folder": "./temp",
  "keep_temp_files": false,
  "vocal_separation": {
    "method": "demucs",
    "model": "htdemucs"
  },
  "speech_to_text": {
    "model": "base",
    "language": "auto"
  },
  "subtitle_format": "ass",
  "logging": {
    "log_folder": "./logs",
    "log_level": "INFO"
  }
}
```

### Configuration Options

- **default_output_folder**: Where to save output files
- **temp_folder**: Temporary working directory
- **keep_temp_files**: Set to `true` to preserve intermediate files
- **vocal_separation.model**: Demucs model (`htdemucs`, `htdemucs_ft`, `mdx_extra`)
- **speech_to_text.model**: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- **speech_to_text.language**: Language code or `auto` for automatic detection
- **subtitle_format**: Output format (`ass`, `srt`, or `both`)

## Output Files

After processing, you'll get:

1. **KTV Audio/Video File**: `<title>_ktv.mp3` or `<title>_ktv.mp4`
   - Stereo audio with LEFT=instrumental, RIGHT=full vocal
2. **Subtitle File**: `<title>_ktv.ass` (or `.srt`)
   - Synchronized with actual singing timing
   - Word-by-word karaoke effects (in .ass format)

### Using the KTV Files

To use your KTV files:
- Load the MP3/MP4 in any media player
- Use the balance/pan control to switch modes:
  - Pan LEFT: Karaoke mode (sing along!)
  - Pan RIGHT: Original song (with vocals)
- Load the subtitle file to see synchronized lyrics

## Packaging into Executable (Windows)

To create a standalone `.exe` file:

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --onefile --name ktv_converter main.py

# The executable will be in the dist/ folder
# dist/ktv_converter.exe
```

### Notes on Packaging

- The executable will be large (~500MB+) due to included AI models
- First run will download Whisper and Demucs models to cache
- FFmpeg must be installed separately and in PATH
- Models are cached in user's home directory

### Creating a Complete Package

For distribution, create a folder with:
```
ktv_converter/
├── ktv_converter.exe
├── config.json
├── README.md
└── ffmpeg.exe (optional, if bundling FFmpeg)
```

## Troubleshooting

### "FFmpeg not found"
- Ensure FFmpeg is installed and in your PATH
- Test: `ffmpeg -version` in terminal

### "Out of memory" during vocal separation
- Use a smaller Demucs model in config.json
- Close other applications
- Process shorter audio files

### Subtitles timing is off
- Try a larger Whisper model (`small` or `medium`)
- Ensure the audio quality is good
- Check that the language is correctly detected

### YouTube download fails
- Ensure you have rights to download the content
- Check your internet connection
- Update yt-dlp: `pip install -U yt-dlp`

## Legal Notice

**IMPORTANT**: This tool is for personal use with content you own or have rights to process.

- Respect YouTube's Terms of Service
- Do not bypass DRM or download copyrighted content without permission
- Use the local file mode for content you own
- The YouTube download feature is provided for convenience with legally accessible content only

## Logs

All processing steps are logged to `logs/ktv_converter_<timestamp>.log`

Check logs for:
- Detailed error messages
- Processing steps and timing
- Model loading information
- Temporary file locations

## Project Structure

```
ktv-converter/
├── main.py              # Entry point and UI
├── downloader.py        # Media download/copy handler
├── audio_processing.py  # FFmpeg, vocal separation, mixing
├── subtitles.py         # Whisper transcription, subtitle generation
├── config.json          # Configuration settings
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .gitignore          # Git ignore patterns
├── logs/               # Log files (created at runtime)
├── temp/               # Temporary files (created at runtime)
└── output/             # Output files (created at runtime)
```

## Credits

This project uses:
- [Demucs](https://github.com/facebookresearch/demucs) - Meta AI vocal separation
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [FFmpeg](https://ffmpeg.org/) - Media processing

## License

This project is provided as-is for personal use. Please respect all applicable copyrights and terms of service when using this tool.
