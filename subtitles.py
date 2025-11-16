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
          - 正在唱：未唱 = 白色，已唱 = 藍色（卡拉 OK 效果）
          - 下一句預告：整句 = 白色
        """
        logger.info(f"Generating ASS subtitles (left/right current + next line): {output_file}")

        segments = transcription.get("segments", [])
        if not segments:
            logger.warning("No segments found in transcription, skipping ASS generation.")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("")
            return output_file

        # ---------- 樣式定義 ----------
        # 顏色說明（BGR）：
        #   &H00FFFFFF = 白
        #   &H00FF0000 = 藍
        #
        # Karaoke (\k) 的規則：
        #   - 沒有 \k 的字幕：用 PrimaryColour
        #   - 有 \k 的字幕：未唱部分 = SecondaryColour，已唱部分 = PrimaryColour
        #
        # 所以：
        #   - Sing*：Primary = 藍、Secondary = 白（白底 → 唱到變藍）
        #   - Next*：Primary = 白、Secondary = 白（整句預告白字）
        ass_header = """[Script Info]
Title: KTV Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; 正在唱：左邊（奇數句）
Style: SingLeft,Arial,48,&H00FF0000,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,1,260,10,90,1
; 正在唱：右邊（偶數句）
Style: SingRight,Arial,48,&H00FF0000,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,3,260,260,50,1
; 下一句預告：左邊（全白）
Style: NextLeft,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,1,260,10,90,1
; 下一句預告：右邊（全白）
Style: NextRight,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,0,3,260,260,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # 之後如果要自己調位置，就改上面四個 Style 的 MarginL/MarginR/MarginV

        def build_karaoke_text(words, fallback_text: str) -> str:
            """
            把一整句變成「一個字一個 \\k」，並且：
            - 總時間 = 原本 words 裡所有 (end-start) 加總
            - 若沒有 words，就用固定速度（每字 30cs）當作退路
            """
            text = fallback_text.strip()
            if not text:
                return ""

            # 1) 算這一句的總長度（centisecond）
            total_cs = 0
            if words:
                for w in words:
                    dur_cs = max(1, int((w["end"] - w["start"]) * 100))
                    total_cs += dur_cs

            # 如果沒有 word 時間（或總長度是 0），給一個簡單預設
            if total_cs <= 0:
                total_cs = 30 * len(text)  # 假設每個字 0.3 秒

            # 2) 依照「字數」平均切時間
            chars = list(text)
            n = len(chars)
            if n == 1:
                return f"{{\\k{total_cs}}}{chars[0]}"

            per = max(1, total_cs // n)
            used = per * (n - 1)
            last = max(1, total_cs - used)

            parts = []
            for i, ch in enumerate(chars):
                dur = per if i < n - 1 else last
                parts.append(f"{{\\k{dur}}}{ch}")
            return "".join(parts)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ass_header)

            # ===== 1. 每句本身的「正在唱」事件（有卡拉 OK） =====
            for idx, seg in enumerate(segments):
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                words = seg.get("words", [])

                # 過濾掉空句或時間為 0 的奇怪 segment
                if not text or end <= start:
                    continue

                style = "SingLeft" if (idx % 2 == 0) else "SingRight"

                start_str = self.format_timestamp_ass(start)
                end_str = self.format_timestamp_ass(end)

                kara_text = build_karaoke_text(words, text)

                # 這個事件負責「正在唱」時的白→藍跑格效果
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{kara_text}\n"
                )

            # ===== 2. 下一句的「預告」事件（純白，不跑格，時間不中斷） =====
            for i in range(len(segments) - 1):
                curr_seg = segments[i]       # 第 i 句（正在唱）
                next_seg = segments[i + 1]   # 第 i+1 句（預告）

                preview_start = curr_seg["start"]
                preview_end = max(curr_seg["end"], next_seg["start"])

                text = next_seg["text"].strip()
                if not text or preview_end <= preview_start:
                    continue

                # 下一句的位置依照「下一句 index 的奇偶」決定左右
                style_next = "NextLeft" if ((i + 1) % 2 == 0) else "NextRight"

                start_str = self.format_timestamp_ass(preview_start)
                end_str = self.format_timestamp_ass(preview_end)

                # ★不要加 \\k，整句維持 PrimaryColour（白色）當作預告
                f.write(
                    f"Dialogue: 0,{start_str},{end_str},{style_next},,0,0,0,,{text}\n"
                )

        logger.info(f"ASS file created (current + next line, fixed colors): {output_file}")
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
