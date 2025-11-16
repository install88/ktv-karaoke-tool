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
        """
        model_size 建議在 config.json 裡調整，例如:
          "speech_to_text": {
              "model": "small",
              "language": "zh"
          }
        """
        self.model_size = model_size
        self.model = None

    # ---------------------------------------------------------
    # Whisper 載入與聽寫
    # ---------------------------------------------------------
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
        """
        真的「聽寫」歌詞的地方。
        已強制 task='transcribe'，避免 Whisper 自己幫你翻譯成英文。
        """
        self.load_model()

        logger.info(f"Transcribing audio: {audio_file}")

        # 明確指定做聽寫，不要翻譯
        transcribe_options = {
            "word_timestamps": True,
            "verbose": False,
            "task": "transcribe",
        }

        # 如果 config.json 指定了語言（例如 "zh"），就塞進去
        if language and language != "auto":
            transcribe_options["language"] = language

        try:
            result = self.model.transcribe(audio_file, **transcribe_options)

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

    # ---------------------------------------------------------
    # 時間格式轉換
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # SRT 產生
    # ---------------------------------------------------------
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
        產生 ASS 字幕（永遠只顯示兩句：當前一句 + 下一句）

        版面：
          - 左邊：奇數句（index 0,2,4,...），高度較高，靠中間一點
          - 右邊：偶數句（index 1,3,5,...），高度較低，靠中間一點
        顏色：
          - 未唱：白色
          - 已唱：藍色跑格（卡拉 OK 效果）

        時間軸：
          - 唱第 i 句時畫面上出現：
                第 i 句：有 \\k 的卡拉 OK（藍字跑格）
                第 i+1 句：純白文字，預告下一句
          - 下一句會從「第 i 句開始唱」一路顯示到「第 i+1 句開始唱」，
            中間不會有整個字幕都消失的空檔。
        """
        logger.info(f"Generating ASS subtitles (left/right current + next line): {output_file}")

        segments = transcription.get("segments", [])
        if not segments:
            logger.warning("No segments found in transcription, skipping ASS generation.")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("")
            return output_file

        # ---------- 樣式定義 ----------
        # 顏色說明（BGR 格式）：
        #   &H00FFFFFF = 白色
        #   &H00FF0000 = 純藍
        #
        # !!!重點!!!
        # 在大多數播放器裡：
        #   PrimaryColour   = 「未唱 / 背景」顏色
        #   SecondaryColour = 「已唱 / 跑格」顏色
        #
        # 所以：
        #   PrimaryColour   設成白色
        #   SecondaryColour 設成藍色
        #
        # 如果你在 VLC / KMPlayer 看起來相反，
        # 就把下面兩個顏色互換即可。
        ass_header = """[Script Info]
Title: KTV Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; 左邊句子（奇數句）：比較高、靠近中間
;  PrimaryColour   = 白（未唱）
;  SecondaryColour = 藍（已唱）
Style: LeftLine,Arial,48,&H00FFFFFF,&H00FF0000,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,1,260,10,90,1
; 右邊句子（偶數句）：比較低、靠近中間
Style: RightLine,Arial,48,&H00FFFFFF,&H00FF0000,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,3,260,260,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # 你之後如果要自己調位置，就改上面這兩行：
        # - 高度：MarginV
        #   LeftLine 的 MarginV=90  (比較大 → 比較高)
        #   RightLine 的 MarginV=50 (比較小 → 靠近底部)
        # - 靠中程度：MarginL / MarginR
        #   數字越大 → 離螢幕邊越遠 → 越靠中間

        def build_karaoke_text(words, fallback_text: str) -> str:
            """
            把 Whisper 的 words 轉成帶 \\k 的卡拉 OK 文字。
            如果沒有 words，就直接用整句文字。
            """
            if not words:
                return fallback_text

            parts = []
            for w in words:
                dur_cs = max(1, int((w["end"] - w["start"]) * 100))  # 秒 → centisecond
                parts.append(f"{{\\k{dur_cs}}}{w['word']}")
            return "".join(parts)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ass_header)

            # ===== 1. 每句本身的「正在唱」事件（有卡拉 OK） =====
            for idx, seg in enumerate(segments):
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                words = seg.get("words", [])

                style = "LeftLine" if (idx % 2 == 0) else "RightLine"

                start_str = self.format_timestamp_ass(start)
                end_str = self.format_timestamp_ass(end)

                kara_text = build_karaoke_text(words, text)

                # 這個事件負責「正在唱」時的藍色跑格效果
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{kara_text}\n"
                )

            # ===== 2. 下一句的「預告」事件（純白，不跑格，時間不中斷） =====
            # 唱第 i 句時，要看到第 i+1 句，並且從第 i 句開始唱
            # 一直到第 i+1 句開始唱為止，中間都不要空白。
            for i in range(len(segments) - 1):
                curr_seg = segments[i]       # 第 i 句（正在唱）
                next_seg = segments[i + 1]   # 第 i+1 句（預告）

                preview_start = curr_seg["start"]
                # 讓預告一直顯示到「下一句開始唱」，不中斷
                preview_end = max(curr_seg["end"], next_seg["start"])

                if preview_end <= preview_start:
                    continue

                style_next = "LeftLine" if ((i + 1) % 2 == 0) else "RightLine"

                start_str = self.format_timestamp_ass(preview_start)
                end_str = self.format_timestamp_ass(preview_end)
                text = next_seg["text"].strip()

                # ★這裡故意不用 \\k，整句維持 PrimaryColour（白色），當作「下一句預告」
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},{style_next},,0,0,0,,{text}\n"
                )

        logger.info(f"ASS file created (left/right current + next line, no gaps): {output_file}")
        return output_file



    # ---------------------------------------------------------
    # 封裝：對外只呼叫這個產生字幕
    # ---------------------------------------------------------
    def generate_subtitles(
        self,
        audio_file: str,
        output_base: str,
        format_type: str = "ass",
        language: Optional[str] = None
    ) -> List[str]:
        """
        audio_file 目前是用「人聲分離後的 vocals 檔」，
        這樣 Whisper 比較不會被伴奏影響。
        """
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
