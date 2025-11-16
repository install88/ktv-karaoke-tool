#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys

#python burn_to_mpg.py --video "output/test1.mp4" --subs "output/test1.ass"
def burn_subtitles_to_mpg(video_file: str, subtitle_file: str, output_file: str):
    """
    使用 ffmpeg 把 ASS 字幕硬燒進畫面，並輸出 MPG（DVD 友善格式）。
    需先安裝 ffmpeg 並設定到 PATH。
    """
    video_path = Path(video_file)
    sub_path = Path(subtitle_file)
    out_path = Path(output_file)

    if not video_path.exists():
        print(f"[ERROR] Video file not found: {video_path}")
        sys.exit(1)
    if not sub_path.exists():
        print(f"[ERROR] Subtitle file not found: {sub_path}")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 這邊用 -vf subtitles=... 直接硬燒 ASS，
    # -target ntsc-dvd 會輸出一個 DVD 友善的 .mpg 檔案。
    cmd = [
        "ffmpeg",
        "-y",                          # 自動覆蓋
        "-i", str(video_path),
        "-vf", f"subtitles={sub_path.as_posix()}",
        "-target", "ntsc-dvd",         # 或 "pal-dvd" 看你 KTV 機器需求
        str(out_path),
    ]

    print("[INFO] Running ffmpeg command:")
    print("       " + " ".join(cmd))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ffmpeg failed with code {e.returncode}")
        sys.exit(e.returncode)

    print(f"[OK] DVD MPG created: {out_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Burn ASS subtitles into MP4 and export as MPG for DVD players."
    )
    parser.add_argument(
        "--video", required=True, help="Input KTV MP4 file (e.g. output/歌名_ktv.mp4)"
    )
    parser.add_argument(
        "--subs", required=True, help="ASS subtitle file (e.g. output/歌名_ktv.ass)"
    )
    parser.add_argument(
        "--out",
        required=False,
        help="Output MPG path (default: same folder, *_ktv_dvd.mpg)",
    )

    args = parser.parse_args()

    video_path = Path(args.video)
    sub_path = Path(args.subs)

    if args.out:
        out_path = Path(args.out)
    else:
        # 預設輸出檔名：歌名_ktv_dvd.mpg
        stem = video_path.stem.replace("_ktv", "")  # 視情況微調
        out_path = video_path.with_name(video_path.stem + "_dvd.mpg")

    burn_subtitles_to_mpg(str(video_path), str(sub_path), str(out_path))


if __name__ == "__main__":
    main()
