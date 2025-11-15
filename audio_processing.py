import os
import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, temp_folder: str = "./temp"):
        self.temp_folder = Path(temp_folder)
        self.temp_folder.mkdir(parents=True, exist_ok=True)

    def extract_audio(self, input_file: str, output_format: str = "wav") -> str:
        logger.info(f"Extracting audio from: {input_file}")
        
        input_path = Path(input_file)
        output_file = self.temp_folder / f"{input_path.stem}_audio.{output_format}"
        
        cmd = [
            'ffmpeg', '-i', str(input_file),
            '-vn',
            '-acodec', 'pcm_s16le' if output_format == 'wav' else 'libmp3lame',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Audio extracted to: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise

    def separate_vocals(self, audio_file: str, model: str = "htdemucs") -> Tuple[str, str]:
        logger.info(f"Separating vocals using Demucs model: {model}")
        
        audio_path = Path(audio_file)
        output_dir = self.temp_folder / "separated"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'demucs',
            '--two-stems', 'vocals',
            '-n', model,
            '-o', str(output_dir),
            str(audio_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            separated_dir = output_dir / model / audio_path.stem
            vocals_file = separated_dir / "vocals.wav"
            instrumental_file = separated_dir / "no_vocals.wav"
            
            if not vocals_file.exists() or not instrumental_file.exists():
                raise FileNotFoundError("Demucs did not produce expected output files")
            
            logger.info(f"Vocals: {vocals_file}")
            logger.info(f"Instrumental: {instrumental_file}")
            
            return str(vocals_file), str(instrumental_file)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Demucs error: {e.stderr}")
            raise

    def create_ktv_stereo_mix(
        self,
        vocals_file: str,
        instrumental_file: str,
        output_file: str,
        vocal_reduction_db: float = -20.0
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
        
        reduced_vocals = vocals + vocal_reduction_db
        
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
            channels=2
        )
        
        output_path = Path(output_file)
        ktv_audio.export(output_path, format="wav")
        
        logger.info(f"KTV stereo mix created: {output_path}")
        return str(output_path)

    def convert_to_mp3(self, input_file: str, output_file: str, bitrate: str = "320k") -> str:
        logger.info(f"Converting to MP3: {output_file}")
        
        cmd = [
            'ffmpeg', '-i', str(input_file),
            '-codec:a', 'libmp3lame',
            '-b:a', bitrate,
            '-y',
            str(output_file)
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
        output_file: str
    ) -> str:
        logger.info(f"Creating MP4 with KTV audio: {output_file}")
        
        if original_video and Path(original_video).exists():
            cmd = [
                'ffmpeg', '-i', str(original_video),
                '-i', str(ktv_audio),
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '320k',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',
                str(output_file)
            ]
        else:
            logger.info("No video available, creating video with static image")
            cmd = [
                'ffmpeg',
                '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:d=1',
                '-i', str(ktv_audio),
                '-filter_complex', '[0:v]loop=-1:1[v];[v]trim=duration=1000[out]',
                '-map', '[out]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-b:a', '320k',
                '-shortest',
                '-y',
                str(output_file)
            ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"MP4 created: {output_file}")
            return str(output_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise
