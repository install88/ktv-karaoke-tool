# How to Run the KTV Converter

## Important: This is a Desktop Application

This KTV Converter is designed as a **desktop CLI application** that runs on-demand, not as a continuous web service.

### Running in Replit (Limited)

Due to disk space limitations in the Replit environment, the heavy AI models (Demucs for vocal separation and Whisper for transcription) cannot be fully installed here. 

You can run the basic system check:
```bash
python test_basic.py
```

### Running Locally (Recommended)

For full functionality, please run this application on your local computer:

1. **Download/clone this project** to your local machine

2. **Install dependencies:**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate it
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   
   # Install all requirements
   pip install -r requirements.txt
   ```

3. **Ensure FFmpeg is installed** on your system (see README.md)

4. **Run the application:**
   ```bash
   python main.py
   ```

5. **Follow the interactive prompts** to convert your media files

### First Run Notes

- First run will download AI models (~1-2GB) to your cache directory
- This is a one-time download
- Processing time depends on audio length (typically 2-5 minutes per song)

### Packaging as Executable

See README.md for instructions on packaging this as a standalone .exe file using PyInstaller.
