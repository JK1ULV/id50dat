"""JPEGの構成と分解。

送信用.datファイルおよび履歴.datファイルのレコード
(1 MCU分のJPEGのエントロピー符号化データ)と、
通常のJPEGファイルとの相互変換を担う低水準モジュール。

量子化テーブルとハフマンテーブルは自前で計算せず、Pillow(内部のlibjpeg)が
エンコードした参照JPEGからDQT・DHTセグメントをそのまま取り出して使う。
"""

from __future__ import annotations

import io
import struct
from functools import lru_cache
from typing import Optional, Sequence

from PIL import Image

from .constants import RECORD_SLOT
from .i18n import tr, trf

__all__ = [
    "quant_table",
    "build_jpeg",
    "decode_jpeg",
    "encode_mcus",
    "RecordTooLargeError",
]


class RecordTooLargeError(ValueError):
    """1 MCU分の符号が384バイトを超えた場合に発生する例外。"""


@lru_cache(maxsize=None)
def _reference_jpeg(q: int) -> bytes:
    """品質値qでPillowにエンコードさせた参照JPEGを返す。"""
    if not 1 <= q <= 100:
        raise ValueError(trf("qは1〜100で指定してください: {q}", q=q))
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (128, 128, 128)).save(
        buf, format="JPEG", quality=q, subsampling="4:2:0", optimize=False
    )
    return buf.getvalue()


def _segments_of(jpeg: bytes, marker: int) -> list[bytes]:
    """JPEGから指定マーカーのセグメント(マーカー込み)を取り出す。"""
    found = []
    i = 2
    while i < len(jpeg):
        m = jpeg[i + 1]
        if m == 0xDA:
            break
        length = struct.unpack(">H", jpeg[i + 2 : i + 4])[0]
        if m == marker:
            found.append(jpeg[i : i + 2 + length])
        i += 2 + length
    return found


@lru_cache(maxsize=None)
def _dqt_segments(q: int) -> bytes:
    """品質値qのDQTセグメント(輝度・色差)を参照JPEGから取り出す。"""
    segments = _segments_of(_reference_jpeg(q), 0xDB)
    if not segments:
        raise ValueError(tr("参照JPEGにDQTが見つかりません"))
    return b"".join(segments)


@lru_cache(maxsize=None)
def _dht_segments() -> bytes:
    """標準ハフマンテーブルのDHTセグメント4本を参照JPEGから取り出す。"""
    segments = _segments_of(_reference_jpeg(50), 0xC4)
    if len(segments) != 4:
        raise ValueError(tr("DHTセグメント数が不正です"))
    return b"".join(segments)


def quant_table(q: int) -> dict[int, list[int]]:
    """品質値qの量子化テーブルを返す(0: 輝度、1: 色差。ラスター順)。"""
    with Image.open(io.BytesIO(_reference_jpeg(q))) as img:
        return {k: list(v) for k, v in img.quantization.items()}


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _sof0_segment(width: int, height: int) -> bytes:
    # YCbCr 4:2:0。Yは2×2、CbおよびCrは1×1のサンプリング比。
    payload = struct.pack(
        ">BHHB", 8, height, width, 3
    ) + bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    return _segment(0xC0, payload)


def _sos_segment() -> bytes:
    payload = bytes([3, 1, 0x00, 2, 0x11, 3, 0x11, 0, 63, 0])
    return _segment(0xDA, payload)


def build_jpeg(
    mcus: Sequence[Optional[bytes]], width: int, height: int, q: int
) -> bytes:
    """MCUごとのJPEGのエントロピー符号化データからJPEGファイルを構成する。

    mcusの要素がNoneまたは空の位置は未受信MCUとして扱い、実データを
    出力せず前後のリスタートマーカーだけで位置を保つ。
    """
    expected = ((width + 15) // 16) * ((height + 15) // 16)
    if len(mcus) != expected:
        raise ValueError(tr("MCU数が一致しません"))
    parts = [
        b"\xFF\xD8",                    # SOI
        _dqt_segments(q),               # DQT ×2
        _sof0_segment(width, height),   # SOF0
        _dht_segments(),                # DHT ×4
        _segment(0xDD, struct.pack(">H", 1)),  # DRI: リスタート間隔1 MCU
        _sos_segment(),                 # SOS
    ]
    last = len(mcus) - 1
    for i, mcu in enumerate(mcus):
        if mcu:
            parts.append(bytes(mcu))
        if i < last:  # 最後のMCUの後ろにはリスタートマーカーを置かない
            parts.append(bytes([0xFF, 0xD0 + (i & 7)]))
    parts.append(b"\xFF\xD9")           # EOI
    return b"".join(parts)


def decode_jpeg(jpeg: bytes) -> Image.Image:
    """JPEGデータをRGBのPillow画像として返す。"""
    with Image.open(io.BytesIO(jpeg)) as image:
        return image.convert("RGB")


def _split_entropy(jpeg: bytes) -> list[bytes]:
    """JPEGのエントロピー符号をリスタートマーカーで分割する。"""
    # SOSセグメントの末尾までスキップする
    i = 2
    while i < len(jpeg):
        if jpeg[i] != 0xFF:
            raise ValueError(trf(
                "マーカーの位置が不正です: offset 0x{offset:X}", offset=i
            ))
        marker = jpeg[i + 1]
        length = struct.unpack(">H", jpeg[i + 2 : i + 4])[0]
        i += 2 + length
        if marker == 0xDA:
            break
    else:
        raise ValueError(tr("SOSが見つかりません"))

    mcus: list[bytes] = []
    current = bytearray()
    while i < len(jpeg):
        b = jpeg[i]
        if b == 0xFF:
            nxt = jpeg[i + 1]
            if nxt == 0x00:  # バイトスタッフィングはデータの一部
                current += jpeg[i : i + 2]
                i += 2
                continue
            if 0xD0 <= nxt <= 0xD7:  # リスタートマーカー
                mcus.append(bytes(current))
                current = bytearray()
                i += 2
                continue
            if nxt == 0xD9:  # EOI
                mcus.append(bytes(current))
                return mcus
            raise ValueError(trf(
                "想定外のマーカーです: FF{marker:02X} (offset 0x{offset:X})",
                marker=nxt,
                offset=i,
            ))
        current.append(b)
        i += 1
    raise ValueError(tr("EOIが見つかりません"))


def encode_mcus(image: Image.Image, q: int) -> list[bytes]:
    """画像をJPEG符号化し、MCUごとのエントロピー符号のリストを返す。

    ST-ID50Wと同じ条件(4:2:0、リスタート間隔1 MCU、標準ハフマンテーブル)
    でPillowにより符号化する。画像の幅と高さは16の倍数であること。
    """
    if image.width % 16 or image.height % 16:
        raise ValueError(trf(
            "幅と高さは16の倍数にしてください: {width}×{height}",
            width=image.width,
            height=image.height,
        ))
    buf = io.BytesIO()
    image.convert("RGB").save(
        buf,
        format="JPEG",
        quality=q,
        subsampling="4:2:0",
        optimize=False,          # 標準ハフマンテーブルを使用
        restart_marker_blocks=1, # リスタート間隔1 MCU
    )
    mcus = _split_entropy(buf.getvalue())
    expected = (image.width // 16) * (image.height // 16)
    if len(mcus) != expected:
        raise ValueError(tr("MCU数が一致しません"))
    for i, mcu in enumerate(mcus):
        if len(mcu) > RECORD_SLOT:
            raise RecordTooLargeError(trf(
                "MCU {index}の符号長（{length}バイト）が上限（{limit}バイト）を超えています",
                index=i,
                length=len(mcu),
                limit=RECORD_SLOT,
            ))
    return mcus
