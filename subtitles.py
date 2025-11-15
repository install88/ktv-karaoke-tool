import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

try:
    import whisper
except ImportError:
    whisper = None

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def load_model(self):
        if whisper is None:
            raise ImportError("OpenAI Whisper is not installed")
        
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")

    def transcribe_audio(self, audio_file: str, language: Optional[str] = None) -> Dict:
        self.load_model()
        
        logger.info(f"Transcribing audio: {audio_file}")
        
        transcribe_options = {
            "word_timestamps": True,
            "verbose": False
        }
        
        if language and language != "auto":
            transcribe_options["language"] = language
        
        result = self.model.transcribe(audio_file, **transcribe_options)
        
        logger.info(f"Transcription completed. Found {len(result.get('segments', []))} segments")
        return result

    def format_timestamp_srt(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def format_timestamp_ass(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def generate_srt(self, transcription: Dict, output_file: str) -> str:
        logger.info(f"Generating SRT subtitles: {output_file}")
        
        segments = transcription.get("segments", [])
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for idx, segment in enumerate(segments, 1):
                start = self.format_timestamp_srt(segment['start'])
                end = self.format_timestamp_srt(segment['end'])
                text = segment['text'].strip()
                
                f.write(f"{idx}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
        
        logger.info(f"SRT file created: {output_file}")
        return output_file

    def generate_ass(self, transcription: Dict, output_file: str) -> str:
        logger.info(f"Generating ASS subtitles with karaoke effects: {output_file}")
        
        segments = transcription.get("segments", [])
        
        ass_header = """[Script Info]
Title: KTV Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000088FF,&H00000000,&H00666666,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
Style: Karaoke,Arial,48,&H0000FFFF,&H00FF00FF,&H00000000,&H00666666,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ass_header)
            
            for segment in segments:
                start = self.format_timestamp_ass(segment['start'])
                end = self.format_timestamp_ass(segment['end'])
                text = segment['text'].strip()
                
                words = segment.get('words', [])
                
                if words and len(words) > 1:
                    karaoke_text = ""
                    for i, word in enumerate(words):
                        word_start = word['start'] - segment['start']
                        word_duration = (word['end'] - word['start']) * 100
                        karaoke_text += f"{{\\k{int(word_duration)}}}{word['word']}"
                    
                    f.write(f"Dialogue: 0,{start},{end},Karaoke,,0,0,0,,{karaoke_text}\n")
                else:
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
        
        logger.info(f"ASS file created with karaoke effects: {output_file}")
        return output_file

    def generate_subtitles(
        self,
        audio_file: str,
        output_base: str,
        format_type: str = "ass",
        language: Optional[str] = None
    ) -> List[str]:
        transcription = self.transcribe_audio(audio_file, language)
        
        generated_files = []
        
        if format_type == "ass" or format_type == "both":
            ass_file = f"{output_base}.ass"
            self.generate_ass(transcription, ass_file)
            generated_files.append(ass_file)
        
        if format_type == "srt" or format_type == "both":
            srt_file = f"{output_base}.srt"
            self.generate_srt(transcription, srt_file)
            generated_files.append(srt_file)
        
        return generated_files
