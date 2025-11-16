#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
小工具說明：
- 給一個 .ass（KTV 字幕檔）和一個 lyrics.txt（正確歌詞，每行一句）
- 會用 lyrics.txt 的文字覆蓋 .ass 內真正「在唱的那一行」（含 \k）
- 時間軸照舊，\k 會依新歌詞「平均切時間」，變成一個字一個字跑
- 不會動到 mp4 / mpg，只是產生一個新的 .ass

使用方法（Windows 建議一行打完）：
    python fix_ass_with_lyrics.py --ass "output/歌名_ktv.ass" --lyrics "output/lyrics.txt"
或指定輸出檔名：
    python fix_ass_with_lyrics.py --ass "output/歌名_ktv.ass" --lyrics "output/lyrics.txt" --out "output/歌名_ktv_fixed.ass"
"""

import argparse
import re
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--ass", required=True, help="原始 .ass 檔路徑")
    p.add_argument("--lyrics", required=True, help="純文字歌詞檔路徑（每行一句）")
    p.add_argument("--out", help="輸出的 .ass 檔路徑（預設為 <原檔名>_fixed.ass）")
    return p.parse_args()


# ---------- 基本小工具 ----------

def ass_time_to_seconds(t: str) -> float:
    """
    ASS 時間格式: H:MM:SS.cc  例如 0:01:23.45
    轉成秒數（float）
    """
    hms, cs = t.split(".")
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0


def seconds_to_centisecs(sec: float) -> int:
    return max(1, int(round(sec * 100)))


def extract_total_k(text: str, fallback_cs: int) -> int:
    """
    從原本的 \k 標籤裡把所有 duration 加總。
    如果沒有任何 \k，就用 fallback_cs 當總長度。
    """
    ks = re.findall(r"\{\\k(\d+)\}", text)
    if not ks:
        return fallback_cs
    total = sum(int(x) for x in ks)
    return total if total > 0 else fallback_cs


def build_kara_from_lyrics(new_line: str, total_cs: int) -> str:
    """
    根據新的歌詞 new_line，把 total_cs 的時間
    平均分給每個字，產出 {\\kNN}字 的字串。
    """
    new_line = new_line.strip()
    if not new_line:
        return ""

    chars = list(new_line)
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


def split_dialogue_fields(line: str):
    """
    ASS Dialogue 行拆欄位工具：
    Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
    Text 欄位可能含逗號，所以最多切 9 次。
    """
    prefix, rest = line.split(":", 1)
    parts = rest.strip().split(",", 9)
    # 如果欄位不足，簡單補空字串避免爆炸
    while len(parts) < 10:
        parts.append("")
    return {
        "prefix": prefix,
        "layer": parts[0],
        "start": parts[1],
        "end": parts[2],
        "style": parts[3],
        "name": parts[4],
        "margin_l": parts[5],
        "margin_r": parts[6],
        "margin_v": parts[7],
        "effect": parts[8],
        "text": parts[9],
    }


def rebuild_dialogue(d):
    """
    把 split_dialogue_fields 的 dict 再組回一行 Dialogue。
    """
    fields = [
        d["layer"],
        d["start"],
        d["end"],
        d["style"],
        d["name"],
        d["margin_l"],
        d["margin_r"],
        d["margin_v"],
        d["effect"],
        d["text"],
    ]
    return f'{d["prefix"]}: {",".join(fields)}'


# ---------- 主流程 ----------

def main():
    args = parse_args()

    ass_path = Path(args.ass)
    lyrics_path = Path(args.lyrics)

    if not ass_path.is_file():
        raise FileNotFoundError(f"ASS 檔不存在: {ass_path}")
    if not lyrics_path.is_file():
        raise FileNotFoundError(f"歌詞檔不存在: {lyrics_path}")

    out_path = Path(args.out) if args.out else ass_path.with_name(ass_path.stem + "_fixed.ass")

    # 1) 讀取歌詞
    with lyrics_path.open("r", encoding="utf-8") as f:
        # 每一行代表一句歌詞，空白行會被略過
        lyrics = [line.strip() for line in f if line.strip()]

    if not lyrics:
        raise ValueError("lyrics.txt 內容為空，至少要有一行歌詞。")

    # 2) 讀取 ASS
    with ass_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    # 把所有 Dialogue 行拆出來
    dialogue_indices = []
    dialogue_objs = []

    for idx, line in enumerate(lines):
        if line.lstrip().startswith("Dialogue:"):
            d = split_dialogue_fields(line)
            d["index"] = idx  # 記住原本位子
            dialogue_indices.append(idx)
            dialogue_objs.append(d)

    # 分成「正在唱」（有 \k）與「預告」（沒有 \k）
    sing_dialogues = [d for d in dialogue_objs if r"\k" in d["text"]]
    preview_dialogues = [d for d in dialogue_objs if r"\k" not in d["text"]]

    if not sing_dialogues:
        print("⚠ 找不到含 \\k 的 Dialogue，可能這個 ASS 不是我們產生的 KTV 格式。")
        return

    # 3) 把 lyrics 對應到 sing_dialogues
    n_sing = len(sing_dialogues)
    n_lyr = len(lyrics)
    n_pair = min(n_sing, n_lyr)

    if n_lyr != n_sing:
        print(f"⚠ 歌詞行數 ({n_lyr}) 與含 \\k 的行數 ({n_sing}) 不一致，只會套前 {n_pair} 行。")

    # 依序套用：第 i 個「在唱的行」 ← lyrics[i]
    for i in range(n_pair):
        d = sing_dialogues[i]
        new_line = lyrics[i]

        # 算總時間（以原 \k 為主，沒有就用 start/end 差）
        start_sec = ass_time_to_seconds(d["start"])
        end_sec = ass_time_to_seconds(d["end"])
        fallback_cs = seconds_to_centisecs(end_sec - start_sec)
        total_cs = extract_total_k(d["text"], fallback_cs)

        # 重新做一份跑字
        d["text"] = build_kara_from_lyrics(new_line, total_cs)

    # 4) 把「預告行」也一起改文字（不帶 \k，只顯示整句）
    #    邏輯：預告行數量 ≈ 歌詞行數 - 1
    #    讓第 i 個預告顯示 lyrics[i+1]
    max_preview = min(len(preview_dialogues), max(0, n_lyr - 1))
    for i in range(max_preview):
        d = preview_dialogues[i]
        d["text"] = lyrics[i + 1]

    # 5) 把更新後的 Dialogue 塞回原本的 lines 陣列
    for d in dialogue_objs:
        idx = d["index"]
        lines[idx] = rebuild_dialogue(d) + "\n"

    # 6) 寫出新的 .ass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✅ 修正完成")
    print(f"  原始 ASS: {ass_path}")
    print(f"  歌詞檔   : {lyrics_path}")
    print(f"  新 ASS   : {out_path}")


if __name__ == "__main__":
    main()
