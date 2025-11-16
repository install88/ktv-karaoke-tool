import os
import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import shutil  # 新增：用來複製音檔，避開中文檔名問題
import sys


try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

logger = logging.getLogger(__name__)


def convert_mp3_to_wav(src_mp3: Path, dst_wav: Path) -> None:
    """
    使用系統 ffmpeg 將 MP3 轉成 WAV。
    """
    cmd = ["ffmpeg", "-y", "-i", str(src_mp3), str(dst_wav)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(
            "ffmpeg failed to convert %s to %s\nSTDOUT:\n%s\nSTDERR:\n%s",
            src_mp3,
            dst_wav,
            result.stdout,
            result.stderr,
        )
        raise RuntimeError(
            f"ffmpeg failed to convert {src_mp3} to {dst_wav} "
            f"(exit code {result.returncode})."
        )

class AudioProcessor:
    def __init__(self, temp_folder: str = "./temp"):
        self.temp_folder = Path(temp_folder)
        self.temp_folder.mkdir(parents=True, exist_ok=True)

    def _build_ffmpeg_subtitle_filter(self, subtitle_file: str) -> str:
        """
        把 Windows 路徑轉成 ffmpeg subtitles 濾鏡可用格式。
        例如：
          C:\\Users\\insta\\...\\foo.ass
        變成：
          filename='C\\:/Users/insta/.../foo.ass'
        """
        p = Path(subtitle_file).absolute()
        s = str(p).replace("\\", "/")   # 變成 / 路徑
        s = s.replace(":", r"\:")       # C: → C\:
        return f"subtitles=filename='{s}'"

    def create_mpg_with_subtitles(
        self,
        video_file: str,
        subtitle_file: str,
        output_file: str,
    ) -> None:
        """
        將「已有的 MP4」+「ASS 字幕」轉成 DVD 播放機比較友善的 MPG：
          - 視訊：MPEG-2
          - 音訊：MP2
          - 字幕：硬燒進畫面（KTV 店用）
        """

        logger = logging.getLogger(__name__)

        # 準備 ffmpeg 指令
        sub_filter = self._build_ffmpeg_subtitle_filter(subtitle_file)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_file),           # 輸入：你第 7 步做好的 _ktv.mp4
            "-vf", sub_filter,               # 硬燒 ASS 字幕
            "-c:v", "mpeg2video",            # DVD 常用的 MPEG-2 視訊
            "-q:v", "2",                     # 畫質（2 算滿不錯，數字越小越好）
            "-c:a", "mp2",                   # MP2 音訊
            "-ar", "48000",                  # 48kHz
            "-b:a", "192k",                  # 192 kbps
            "-aspect", "16:9",               # 大多數 MV 都是 16:9
            str(output_file),
        ]

        logger.info("Running ffmpeg (MPG with subtitles): %s", " ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(
                "ffmpeg (mpg) failed:\nSTDOUT:\n%s\nSTDERR:\n%s",
                result.stdout,
                result.stderr,
            )
            raise RuntimeError(
                f"ffmpeg failed when creating MPG with subtitles.\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        logger.info("MPG file with burned subtitles created: %s", output_file)           


    def extract_audio(self, input_file: str, output_format: str = "wav") -> str:
        logger.info(f"Extracting audio from: {input_file}")
        
        input_path = Path(input_file)
        output_file = self.temp_folder / f"{input_path.stem}_audio.{output_format}"
        
        cmd = [
            "ffmpeg", "-i", str(input_file),
            "-vn",
            "-acodec", "pcm_s16le" if output_format == "wav" else "libmp3lame",
            "-ar", "44100",
            "-ac", "2",
            "-y",
            str(output_file),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Audio extracted to: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise

    def separate_vocals(self, audio_file: str, model: str = "htdemucs") -> Tuple[str, str]:
        """
        使用 Demucs 將音檔分離成人聲與伴奏。

        為了避免 Windows 在中文路徑 / 特殊字元編碼出問題，
        先把音檔複製成一個純英文檔名，再丟給 Demucs 處理。
        然後使用 --mp3 讓 Demucs 輸出 mp3，再用 ffmpeg 轉成 wav。
        """
        logger.info(f"Separating vocals using Demucs model: {model}")
        
        audio_path = Path(audio_file)
        output_dir = self.temp_folder / "separated"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 使用簡單英文檔名，避免 Demucs/Windows 對中文路徑出問題
        safe_basename = "ktv_input_audio"
        safe_audio_path = self.temp_folder / f"{safe_basename}{audio_path.suffix}"
        shutil.copy2(audio_path, safe_audio_path)

        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "--mp3",                 # ⭐ 用 MP3 存檔，避開 torchaudio.save / torchcodec
            "-n", model,
            "-o", str(output_dir),
            str(safe_audio_path),
        ]

        try:
            # 不用 check=True，這樣就算失敗也能拿到 stdout/stderr
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            logger.error("Demucs command not found")
            raise RuntimeError(
                "Demucs is not installed or not in PATH. Please install it with: pip install demucs\n"
                "Note: Demucs requires significant disk space (~2GB) and PyTorch."
            ) from e

        # 如果 Demucs 回傳非 0，直接把訊息印出來
        if result.returncode != 0:
            logger.error(
                "Demucs failed with code %s\nSTDOUT:\n%s\nSTDERR:\n%s",
                result.returncode,
                result.stdout,
                result.stderr,
            )
            raise RuntimeError(
                f"Demucs vocal separation failed (exit code {result.returncode}).\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n"
                "This may be due to insufficient memory, missing PyTorch, or model download failure."
            )

        # --- 這裡改成搜尋 mp3，然後用 ffmpeg 轉成 wav ---
        vocals_mp3_candidates = list(output_dir.rglob("vocals.mp3"))
        no_vocals_mp3_candidates = list(output_dir.rglob("no_vocals.mp3"))

        if not vocals_mp3_candidates or not no_vocals_mp3_candidates:
            existing_mp3 = list(output_dir.rglob("*.mp3"))
            logger.error(
                "Demucs finished but expected MP3 files are missing.\n"
                "Found these .mp3 files under %s:\n%s",
                output_dir,
                "\n".join(str(p) for p in existing_mp3) if existing_mp3 else "(no mp3 files)",
            )
            raise RuntimeError(
                "Demucs processing completed but output MP3 files are missing.\n"
                f"Searched under: {output_dir}\n"
                f"Found vocals.mp3: {vocals_mp3_candidates}\n"
                f"Found no_vocals.mp3: {no_vocals_mp3_candidates}\n"
                "This may indicate a processing error or an unexpected output layout."
            )

        # 目前先拿第一個匹配到的檔案
        vocals_mp3 = vocals_mp3_candidates[0]
        instrumental_mp3 = no_vocals_mp3_candidates[0]

        # 在同一個資料夾底下產生對應的 wav
        vocals_wav = vocals_mp3.with_suffix(".wav")
        instrumental_wav = instrumental_mp3.with_suffix(".wav")

        convert_mp3_to_wav(vocals_mp3, vocals_wav)
        convert_mp3_to_wav(instrumental_mp3, instrumental_wav)

        logger.info(f"Vocals (wav): {vocals_wav}")
        logger.info(f"Instrumental (wav): {instrumental_wav}")
        
        return str(vocals_wav), str(instrumental_wav)


    def create_ktv_stereo_mix(
        self,
        vocals_file: str,
        instrumental_file: str,
        output_file: str,
        vocal_reduction_db: float = -20.0,
    ) -> str:
        logger.info("Creating KTV stereo mix")
        
        if AudioSegment is None:
            raise ImportError("pydub is not installed")
        
        vocals = AudioSegment.from_wav(vocals_file)
        instrumental = AudioSegment.from_wav(instrumental_file)
        
        if len(vocals) != len(instrumental):
            min_length = min(len(vocals), len(instrumental))
            vocals = vocals[:min_length]
            instrumental = instrumental[:min_length]
        
        reduced_vocals = vocals + vocal_reduction_db  # 目前沒用到，但先保留
        
        left_channel = instrumental
        right_channel = instrumental.overlay(vocals)
        
        left_samples = np.array(left_channel.get_array_of_samples())
        right_samples = np.array(right_channel.get_array_of_samples())
        
        if left_channel.channels == 2:
            left_samples = left_samples[::2]
        if right_channel.channels == 2:
            right_samples = right_samples[::2]
        
        min_len = min(len(left_samples), len(right_samples))
        left_samples = left_samples[:min_len]
        right_samples = right_samples[:min_len]
        
        stereo_samples = np.empty((min_len * 2,), dtype=left_samples.dtype)
        stereo_samples[0::2] = left_samples
        stereo_samples[1::2] = right_samples
        
        ktv_audio = AudioSegment(
            stereo_samples.tobytes(),
            frame_rate=left_channel.frame_rate,
            sample_width=left_channel.sample_width,
            channels=2,
        )
        
        output_path = Path(output_file)
        ktv_audio.export(output_path, format="wav")
        
        logger.info(f"KTV stereo mix created: {output_path}")
        return str(output_path)

    def convert_to_mp3(self, input_file: str, output_file: str, bitrate: str = "320k") -> str:
        logger.info(f"Converting to MP3: {output_file}")
        
        cmd = [
            "ffmpeg", "-i", str(input_file),
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            "-y",
            str(output_file),
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"MP3 created: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise

    def create_video_with_audio(
        self,
        original_video: Optional[str],
        ktv_audio: str,
        output_file: str,
    ) -> str:
        logger.info(f"Creating MP4 with KTV audio: {output_file}")
        
        if original_video and Path(original_video).exists():
            cmd = [
                "ffmpeg", "-i", str(original_video),
                "-i", str(ktv_audio),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "320k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y",
                str(output_file),
            ]
        else:
            logger.info("No video available, creating video with static image")
            cmd = [
                "ffmpeg",
                "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1",
                "-i", str(ktv_audio),
                "-filter_complex", "[0:v]loop=-1:1[v];[v]trim=duration=1000[out]",
                "-map", "[out]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "320k",
                "-shortest",
                "-y",
                str(output_file),
            ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"MP4 created: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise

    def create_video_with_audio_and_subtitles(
        self,
        original_video: Optional[str],
        ktv_audio: str,
        ass_subtitle: Optional[str],
        output_file: str,
    ) -> str:
        """
        建立「已內嵌 ASS 字幕」的 MP4。
        - original_video：原始 MV 檔（有畫面）
        - ktv_audio：你混好、左右聲道不同內容的 KTV 音訊
        - ass_subtitle：ASS 字幕（含顏色 / \k 效果）
        - output_file：輸出的 mp4

        注意：因為加了 -vf subtitles，要重新編碼影片，無法用 -c:v copy。
        """
        logger.info(f"Creating MP4 with KTV audio + hardcoded ASS subtitles: {output_file}")

        # 沒有原始影片的情況，就退回用原本的 create_video_with_audio
        if not original_video or not Path(original_video).exists():
            logger.warning("Original video not found, falling back to audio-only video creation.")
            return self.create_video_with_audio(None, ktv_audio, output_file)

        # 如果沒給字幕檔，一樣退回舊方法
        if not ass_subtitle or not Path(ass_subtitle).exists():
            logger.warning("ASS subtitle file not found, falling back to video without burned subtitles.")
            return self.create_video_with_audio(original_video, ktv_audio, output_file)

        # Windows / ffmpeg 的 subtitles 濾鏡對路徑很機車，保守一點把路徑處理一下
        ass_path = Path(ass_subtitle).resolve()
        # 換成正斜線，並把 : escape 掉，避免 C:\ 之類出問題
        ass_for_filter = str(ass_path).replace("\\", "/").replace(":", r"\:")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(original_video),
            "-i", str(ktv_audio),
            # 字幕濾鏡：這一步會把 ASS 字幕「燒進」影片畫面
            "-vf", f"subtitles={ass_for_filter}",
            # 影片要重新編碼（不能再 copy）
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",          # 品質可自行調整（數字越大品質越差、檔案越小）
            # 音訊用 AAC
            "-c:a", "aac",
            "-b:a", "320k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_file),
        ]

        try:
            import subprocess
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"ffmpeg stdout:\n{result.stdout}")
            logger.info(f"MP4 with hardcoded subtitles created: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error while burning subtitles:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")
            raise            
