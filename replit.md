# KTV Converter - Project Documentation

## Project Overview

This is a Python desktop application (not a web app) that converts YouTube videos or local media files into karaoke-style (KTV) files with synchronized subtitles. The application is designed to be packaged into a standalone executable for Windows/macOS/Linux.

### Purpose
- Convert media files to KTV format with special stereo audio mixing
- Generate synchronized subtitles that follow actual singing timing
- Support both YouTube downloads and local file processing

### Current State
- Terminal-based application with interactive prompts
- Modular architecture ready for GUI integration
- Production-ready for local usage and executable packaging

## Recent Changes

### 2025-11-15: Initial Implementation + Bug Fixes
- Created complete KTV converter application
- Implemented modular architecture with separate modules:
  - `main.py`: Terminal UI and orchestration
  - `downloader.py`: YouTube/local file handling
  - `audio_processing.py`: FFmpeg, vocal separation, KTV mixing
  - `subtitles.py`: Whisper transcription and subtitle generation
- Added comprehensive README with setup and packaging instructions
- Configured for Python 3.11 with FFmpeg system dependency

**Critical Fixes Applied:**
- Fixed cleanup timing: temp files now deleted AFTER final output creation (not before)
- Added try-finally block to ensure cleanup happens even on errors
- Enhanced error handling for Demucs and Whisper with helpful installation messages
- Improved video source validation to prevent missing file errors
- Subtitles correctly saved directly to output folder (no packaging needed)

## Project Architecture

### Tech Stack
- **Language**: Python 3.11
- **Audio Processing**: FFmpeg (system)
- **Vocal Separation**: Demucs (Facebook Research AI)
- **Speech-to-Text**: OpenAI Whisper
- **Audio Manipulation**: pydub
- **YouTube Download**: yt-dlp

### Module Structure

```
main.py - Entry point, user interface, orchestration
├── downloader.py - Media acquisition (YouTube/local)
├── audio_processing.py - Audio extraction, separation, mixing
└── subtitles.py - Transcription and subtitle generation
```

### Key Features
1. **KTV Stereo Mix**: LEFT channel (instrumental only), RIGHT channel (full vocals)
2. **Synchronized Subtitles**: Word-by-word timing using Whisper timestamps
3. **Karaoke Effects**: ASS format with karaoke tags for color transitions
4. **Flexible Input**: YouTube URLs or local video/audio files
5. **Format Options**: Output as MP3 (audio) or MP4 (video)

### Processing Pipeline
1. Input validation (URL or file path)
2. Media download/copy to temp folder
3. Audio extraction using FFmpeg
4. Vocal separation using Demucs AI
5. KTV stereo mixing (LEFT=instrumental, RIGHT=full)
6. Lyric transcription using Whisper
7. Subtitle generation (ASS/SRT with karaoke timing)
8. Final file creation (MP3 or MP4)

## User Preferences

### Usage Pattern
- This is a command-line application, not a web service
- No workflow needed - runs on-demand via `python main.py`
- Terminal-based interface with interactive prompts
- All processing happens locally (no server required)

### Important Notes
- First run downloads AI models (Whisper + Demucs) - can be slow
- Models are cached in user's home directory (~/.cache)
- Processing time depends on audio length (typically 2-5 minutes per song)
- Requires significant disk space for temporary files during processing

## Dependencies

### System Dependencies
- Python 3.11
- FFmpeg (audio/video processing)

### Python Libraries
- yt-dlp (YouTube downloads)
- openai-whisper (speech recognition)
- demucs (vocal separation)
- pydub (audio manipulation)
- numpy (numerical operations)
- pyinstaller (executable packaging)

## Configuration

### config.json Settings
- Output folder, temp folder, file retention
- Demucs model selection (htdemucs, mdx_extra)
- Whisper model size (tiny, base, small, medium, large)
- Subtitle format preference (ass, srt, both)
- Logging configuration

## Deployment Notes

### This is NOT a Web Application
- No web server needed
- No deployment to hosting platform
- Application runs locally on user's computer

### Packaging for Distribution
- Use PyInstaller to create standalone executable
- Executable includes all Python dependencies
- FFmpeg must be installed separately or bundled
- Models download on first run (~1-2GB cache)

### Target Platforms
- Windows: .exe via PyInstaller
- macOS: .app bundle via PyInstaller
- Linux: Standalone binary via PyInstaller

## Legal Considerations

### YouTube Downloads
- yt-dlp download functionality must respect YouTube TOS
- Users responsible for ensuring content rights
- Local file mode available for user-owned content
- Download function abstracted for easy replacement

### Copyright
- Tool designed for personal use with owned content
- No DRM bypassing
- User assumes legal responsibility for content processing
