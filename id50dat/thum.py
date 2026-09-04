"""THUM(128×96画素、1画素1ビットのサムネイル)の復号と生成。

画像は高さ8画素の帯12本に分かれ、各帯が左から右へ128バイトずつ並ぶ。
1バイトは縦8画素を表し、bit 0が帯の上端、bit 7が下端、値1が黒である。
"""

from __future__ import annotations

from PIL import Image

from .constants import THUM_HEIGHT, THUM_PAYLOAD_SIZE, THUM_WIDTH
from .i18n import tr

__all__ = ["decode_thum", "encode_thum", "make_thum"]


def decode_thum(data: bytes) -> Image.Image:
    """1,536バイトのTHUMペイロードをモノクロ画像(mode "1")へ復号する。"""
    if len(data) != THUM_PAYLOAD_SIZE:
        raise ValueError(tr("THUMデータのサイズが不正です"))
    img = Image.new("1", (THUM_WIDTH, THUM_HEIGHT), 1)  # 1=白
    px = img.load()
    for i, byte in enumerate(data):
        x = i % THUM_WIDTH
        y_base = (i // THUM_WIDTH) * 8
        for b in range(8):
            if (byte >> b) & 1:
                px[x, y_base + b] = 0  # 黒
    return img


def encode_thum(img: Image.Image) -> bytes:
    """モノクロ画像をTHUMペイロード(1,536バイト)へ変換する。"""
    if img.size != (THUM_WIDTH, THUM_HEIGHT):
        raise ValueError(tr("THUM画像の解像度が不正です"))
    mono = img.convert("1")
    px = mono.load()
    data = bytearray(THUM_PAYLOAD_SIZE)
    for i in range(THUM_PAYLOAD_SIZE):
        x = i % THUM_WIDTH
        y_base = (i // THUM_WIDTH) * 8
        byte = 0
        for b in range(8):
            if px[x, y_base + b] == 0:  # 黒
                byte |= 1 << b
        data[i] = byte
    return bytes(data)


def make_thum(image: Image.Image) -> bytes:
    """カラー画像からTHUMペイロードを生成する。

    Bicubicで128×96へ縮小し、グレースケール化した後、Pillowの
    Floyd–Steinberg法で二値化する。
    """
    small = image.convert("RGB").resize(
        (THUM_WIDTH, THUM_HEIGHT), Image.Resampling.BICUBIC
    )
    mono = small.convert("L").convert("1")  # Floyd–Steinbergディザリング
    return encode_thum(mono)
