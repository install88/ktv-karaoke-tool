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
            raise RuntimeError(
                "OpenAI Whisper is not installed. Please install it with: pip install openai-whisper\n"
                "Note: Whisper requires PyTorch and significant disk space for models."
            )
        
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            try:
                self.model = whisper.load_model(self.model_size)
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise RuntimeError(
                    f"Failed to load Whisper model '{self.model_size}'. Error: {e}\n"
                    "The model will be downloaded on first use, which requires internet connection."
                ) from e

    def transcribe_audio(self, audio_file: str, language: Optional[str] = None) -> Dict:
        self.load_model()
        
        logger.info(f"Transcribing audio: {audio_file}")
        
        # transcribe_options = {
        #     "word_timestamps": True,
        #     "verbose": False
        # }
        # CHANGED: 明確指定 task="transcribe"，避免做翻譯
        transcribe_options = {
            "word_timestamps": True,
            "verbose": False,
            "task": "transcribe",   # ★ 新增：強制做聽寫，不要翻譯成英文
        }        
        
        # 如果 config.json 指定了語言（例如 "zh"），就塞進去
        if language and language != "auto":
            transcribe_options["language"] = language
        
        try:
            result = self.model.transcribe(audio_file, **transcribe_options)
            
            # NEW: 把 Whisper 自動偵測到的語言印出來，方便你確認
            detected_lang = result.get("language", "unknown")
            logger.info(
                f"Transcription completed. Detected language={detected_lang}, "
                f"segments={len(result.get('segments', []))}"
            )
            return result
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(
                f"Whisper transcription failed. Error: {e}\n"
                "This may be due to audio format issues or insufficient memory."
            ) from e

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
        """
        產生 ASS 卡拉 OK 字幕（永遠顯示：當前一句 + 下一句）

        時間軸邏輯：
          - 第 i 句在唱：顯示
                SingLine：第 i 句（藍色、有 \\k）
                NextLine：第 i+1 句（白色）
          - 第 i 句當「下一句」顯示的時間 = 第 i-1 句在唱的時間
        """
        logger.info(f"Generating ASS subtitles (current + next line): {output_file}")

        segments = transcription.get("segments", [])
        if not segments:
            logger.warning("No segments found in transcription, skipping ASS generation.")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("")
            return output_file

        # ---------- 樣式定義：上行 = 下一句、下行 = 正在唱 ----------
        ass_header = """[Script Info]
Title: KTV Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; 上面那行：下一句（白色，不變色）
Style: NextLine,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,80,1
; 下面那行：正在唱的句子（未唱白、已唱藍）
Style: SingLine,Arial,48,&H00FFFFFF,&H0000FF00,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        def build_karaoke_text(words, fallback_text: str) -> str:
            """
            把 Whisper 的 words 轉成帶 \\k 的卡拉 OK 文字。
            如果沒 words，就直接用整句文字。
            """
            if not words:
                return fallback_text

            parts = []
            for w in words:
                dur_cs = max(1, int((w["end"] - w["start"]) * 100))  # 轉成 centisecond
                parts.append(f"{{\\k{dur_cs}}}{w['word']}")
            return "".join(parts)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ass_header)

            # ===== 1. 為每一句建立「正在唱」的 SingLine 事件 =====
            for seg in segments:
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                words = seg.get("words", [])

                start_str = self.format_timestamp_ass(start)
                end_str = self.format_timestamp_ass(end)

                kara_text = build_karaoke_text(words, text)

                # 下行：當前正在唱的句子（白→藍）
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},SingLine,,0,0,0,,{kara_text}\n"
                )

            # ===== 2. 為每一句建立「當下一句」時期的 NextLine 事件 =====
            # 第 0 句前面沒有「上一句」，所以「被當成下一句」的時段只有從第 0 句開始往後。
            for i in range(1, len(segments)):
                prev_seg = segments[i - 1]   # 前一句
                seg = segments[i]            # 這一句，當「下一句」顯示時

                # 顯示時間：整個「前一句在唱」的時間
                next_start = prev_seg["start"]
                next_end = prev_seg["end"]

                # 如果時間不合理就跳過
                if next_end <= next_start:
                    continue

                start_str = self.format_timestamp_ass(next_start)
                end_str = self.format_timestamp_ass(next_end)

                text = seg["text"].strip()

                # 上行：下一句，純白字，不做 \\k 動畫
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},NextLine,,0,0,0,,{text}\n"
                )

        logger.info(f"ASS file created (current + next line): {output_file}")
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
