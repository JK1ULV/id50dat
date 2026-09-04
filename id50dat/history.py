"""ID-50の送信履歴.datファイルと受信履歴.datファイルの読み取り。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, TypeAlias

from PIL import Image, ImageColor, ImageDraw

from . import jpegio, thum
from .constants import (
    FILENAME_ENCODING,
    MAGIC,
    ENCODE_HEIGHTS,
    QUALITY_NAMES,
    QUALITY_Q,
    RESOLUTIONS,
    RX_HISTORY_SIZE,
    RXH_BITMAP_OFFSET,
    RXH_BITMAP_SIZE,
    RXH_CALLSIGN_FROM_OFFSET,
    RXH_CALLSIGN_TO_OFFSET,
    RXH_DATA_LENGTH,
    RXH_DATA_OFFSET,
    RXH_DATA_RECORDS_OFFSET,
    RXH_DATETIME_OFFSET,
    RXH_HEAD_LENGTH,
    RXH_HEAD_OFFSET,
    RXH_NUMBER_OFFSET,
    RXH_RESOLUTION_OFFSET,
    RXH_QUALITY_OFFSET,
    THUM_PAYLOAD_SIZE,
    TX_HISTORY_SIZE,
    TXH_CALLSIGN_OWN_OFFSET,
    TXH_CALLSIGN_TO_OFFSET,
    TXH_DATA_LENGTH,
    TXH_DATA_OFFSET,
    TXH_DATA_RECORDS_OFFSET,
    TXH_DATETIME_OFFSET,
    TXH_HEAD_LENGTH,
    TXH_HEAD_OFFSET,
    TXH_NUMBER_OFFSET,
    TXH_QUALITY_OFFSET,
    TXH_RESOLUTION_OFFSET,
    TXH_SOURCE_NAME_OFFSET,
    TXH_THUM_OFFSET,
    TXH_THUM_LENGTH,
    TYPE_OFFSET,
    TYPE_RX_HISTORY,
    TYPE_TX_HISTORY,
    mcu_count,
)
from .i18n import tr, trf
from .txdat import read_records

RGBColor: TypeAlias = tuple[int, int, int]
MissingValue: TypeAlias = str | RGBColor
ResolvedMissing: TypeAlias = Literal["transparent"] | RGBColor

__all__ = ["TxHistory", "RxHistory", "resolve_missing"]


def resolve_missing(value: MissingValue = "black") -> ResolvedMissing:
    """未受信MCUの塗りつぶし方法をRGB色または透明化指定へ正規化する。"""
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.lower() == "transparent":
            return "transparent"
        if len(normalized) == 6 and all(
            char in "0123456789abcdefABCDEF" for char in normalized
        ):
            normalized = f"#{normalized}"
        try:
            color = ImageColor.getrgb(normalized)
        except ValueError as e:
            raise ValueError(tr(
                "色名またはRGB値（例: navy, ff8800）を指定してください"
            )) from e
        if len(color) != 3:
            raise ValueError(tr("RGBの色名またはRGB値を指定してください"))
        return color

    if not isinstance(value, tuple) or len(value) != 3:
        raise TypeError(tr("missingには色名、RGB値、またはRGBタプルを指定してください"))
    if any(
        not isinstance(channel, int) or isinstance(channel, bool) for channel in value
    ):
        raise TypeError(tr("RGBタプルの各要素は0〜255の整数にしてください"))
    if any(not 0 <= channel <= 255 for channel in value):
        raise ValueError(tr("RGBタプルの各要素は0〜255にしてください"))
    return value


def _callsign(data: bytes, offset: int) -> str:
    return data[offset : offset + 8].decode("ascii", "replace").rstrip()


def _bcd_datetime(data: bytes, offset: int) -> str:
    """BCDの7バイト(年2、月日時分秒各1)を文字列にする。"""
    b = data[offset : offset + 7]
    try:
        y = int(f"{b[0]:02x}{b[1]:02x}")
        mo, d, h, mi, s = (int(f"{v:02x}") for v in b[2:7])
        return f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}"
    except ValueError:
        return b.hex()


def _history_jpeg(records: list[Optional[bytes]], res: int, qual: int) -> bytes:
    width, height = RESOLUTIONS[res]
    return jpegio.build_jpeg(records, width, height, QUALITY_Q[qual])


def _require_region(data: bytes, offset: int, ident: bytes, length: int) -> None:
    """識別文字列と領域サイズを確認する。"""
    actual_ident = data[offset : offset + 4]
    if actual_ident != ident:
        shown = actual_ident.decode("ascii", "replace")
        raise ValueError(
            trf(
                "{ident}領域が見つかりません: {shown!r}",
                ident=ident.decode(),
                shown=shown,
            )
        )
    actual_length = int.from_bytes(data[offset + 4 : offset + 8], "little")
    if actual_length != length:
        raise ValueError(
            trf(
                "{ident}領域のサイズが不正です",
                ident=ident.decode(),
            )
        )


@dataclass
class TxHistory:
    """送信履歴(TX Picture History)。デコード専用。"""

    callsign_own: str
    callsign_to: str
    number: int
    datetime: str
    resolution: int
    quality: int
    source_name: str          # 元となった送信用.datファイル名
    thum: bytes
    records: list[bytes]      # 使用レコードのみ(MCU数ぶん)

    kind = "tx_history"

    @classmethod
    def parse(cls, data: bytes) -> "TxHistory":
        if len(data) != TX_HISTORY_SIZE:
            raise ValueError(tr("送信履歴のファイルサイズが不正です"))
        if not data.startswith(MAGIC):
            raise ValueError(tr("ファイル先頭の識別子がID-50ではありません"))
        if data[TYPE_OFFSET : TYPE_OFFSET + len(TYPE_TX_HISTORY)] != TYPE_TX_HISTORY:
            raise ValueError(tr("TX Picture History形式のファイルではありません"))
        _require_region(data, TXH_HEAD_OFFSET, b"HEAD", TXH_HEAD_LENGTH)
        _require_region(data, TXH_THUM_OFFSET, b"THUM", TXH_THUM_LENGTH)
        _require_region(data, TXH_DATA_OFFSET, b"DATA", TXH_DATA_LENGTH)
        res = data[TXH_RESOLUTION_OFFSET]
        qual = data[TXH_QUALITY_OFFSET]
        if res not in RESOLUTIONS or qual not in QUALITY_Q:
            raise ValueError(trf(
                "解像度または画質のコードが不正です: {resolution}, {quality}",
                resolution=res,
                quality=qual,
            ))
        name_field = data[TXH_SOURCE_NAME_OFFSET : TXH_SOURCE_NAME_OFFSET + 32]
        source_name = name_field.split(b"\x00", 1)[0].decode(
            FILENAME_ENCODING, "replace"
        )
        records = read_records(data, TXH_DATA_RECORDS_OFFSET, mcu_count(res))
        return cls(
            callsign_own=_callsign(data, TXH_CALLSIGN_OWN_OFFSET),
            callsign_to=_callsign(data, TXH_CALLSIGN_TO_OFFSET),
            number=data[TXH_NUMBER_OFFSET],
            datetime=_bcd_datetime(data, TXH_DATETIME_OFFSET),
            resolution=res,
            quality=qual,
            source_name=source_name,
            thum=bytes(
                data[TXH_THUM_OFFSET + 8 : TXH_THUM_OFFSET + 8 + THUM_PAYLOAD_SIZE]
            ),
            records=records,
        )

    @classmethod
    def load(cls, path) -> "TxHistory":
        with open(path, "rb") as f:
            return cls.parse(f.read())

    def to_jpeg(self) -> bytes:
        return _history_jpeg(list(self.records), self.resolution, self.quality)

    def thum_image(self) -> Image.Image:
        return thum.decode_thum(self.thum)

    def to_image(self) -> Image.Image:
        """JPEGをRGBのPillow画像として返す。"""
        return jpegio.decode_jpeg(self.to_jpeg())

    def describe(self) -> str:
        w, h = RESOLUTIONS[self.resolution]
        return "\n".join(
            (
                trf(
                    "送信履歴  {own} -> {destination}  {datetime}",
                    own=self.callsign_own,
                    destination=self.callsign_to,
                    datetime=self.datetime,
                ),
                trf(
                    "  解像度: {width}×{height}  画質: {quality} (q{q})",
                    width=w,
                    height=h,
                    quality=tr(QUALITY_NAMES[self.quality]),
                    q=QUALITY_Q[self.quality],
                ),
                trf("  元ファイル: {source}", source=self.source_name),
            )
        )


@dataclass
class RxHistory:
    """受信履歴(RX Picture History)。デコード専用。"""

    callsign_from: str
    callsign_to: str
    number: int
    datetime: str
    resolution: int
    quality: int
    received: list[bool]                 # MCUごとの受信フラグ
    records: list[Optional[bytes]]       # 未受信MCUはNone

    kind = "rx_history"

    @classmethod
    def parse(cls, data: bytes) -> "RxHistory":
        if len(data) != RX_HISTORY_SIZE:
            raise ValueError(tr("受信履歴のファイルサイズが不正です"))
        if not data.startswith(MAGIC):
            raise ValueError(tr("ファイル先頭の識別子がID-50ではありません"))
        if data[TYPE_OFFSET : TYPE_OFFSET + len(TYPE_RX_HISTORY)] != TYPE_RX_HISTORY:
            raise ValueError(tr("RX Picture History形式のファイルではありません"))
        _require_region(data, RXH_HEAD_OFFSET, b"HEAD", RXH_HEAD_LENGTH)
        _require_region(data, RXH_DATA_OFFSET, b"DATA", RXH_DATA_LENGTH)
        res = data[RXH_RESOLUTION_OFFSET]
        qual = data[RXH_QUALITY_OFFSET]
        if res not in RESOLUTIONS or qual not in QUALITY_Q:
            raise ValueError(trf(
                "解像度または画質のコードが不正です: {resolution}, {quality}",
                resolution=res,
                quality=qual,
            ))
        count = mcu_count(res)
        bitmap = data[RXH_BITMAP_OFFSET : RXH_BITMAP_OFFSET + RXH_BITMAP_SIZE]
        received = [
            bool(bitmap[i // 8] >> (7 - i % 8) & 1) for i in range(count)
        ]
        raw = read_records(data, RXH_DATA_RECORDS_OFFSET, count)
        records: list[Optional[bytes]] = [
            rec if flag and rec else None for rec, flag in zip(raw, received)
        ]
        return cls(
            callsign_from=_callsign(data, RXH_CALLSIGN_FROM_OFFSET),
            callsign_to=_callsign(data, RXH_CALLSIGN_TO_OFFSET),
            number=data[RXH_NUMBER_OFFSET],
            datetime=_bcd_datetime(data, RXH_DATETIME_OFFSET),
            resolution=res,
            quality=qual,
            received=received,
            records=records,
        )

    @classmethod
    def load(cls, path) -> "RxHistory":
        with open(path, "rb") as f:
            return cls.parse(f.read())

    @property
    def missing_count(self) -> int:
        return sum(1 for r in self.records if r is None)

    def _to_jpeg_with_color(self, missing_color: RGBColor) -> bytes:
        """JPEGを構成する。未受信MCUは指定色で塗りつぶす。"""
        if not self.missing_count:
            return _history_jpeg(self.records, self.resolution, self.quality)

        width, _height = RESOLUTIONS[self.resolution]
        fill_image = Image.new(
            "RGB", (width, ENCODE_HEIGHTS[self.resolution]), missing_color
        )
        fill_records = jpegio.encode_mcus(fill_image, QUALITY_Q[self.quality])
        records = [
            record if record is not None else fill_records[index]
            for index, record in enumerate(self.records)
        ]
        return _history_jpeg(records, self.resolution, self.quality)

    def to_jpeg(self, missing: MissingValue = "black") -> bytes:
        """JPEGを構成する。未受信MCUは指定色で塗りつぶす。"""
        resolved = resolve_missing(missing)
        if resolved == "transparent":
            raise ValueError(tr("transparentはJPEG出力では指定できません"))
        return self._to_jpeg_with_color(resolved)

    def to_image(self, missing: MissingValue = "black") -> Image.Image:
        """未受信MCUを塗りつぶした画像を返す。透明化時はRGBA画像になる。"""
        resolved = resolve_missing(missing)
        transparent = resolved == "transparent"
        color = (0, 0, 0) if transparent else resolved
        result = jpegio.decode_jpeg(self._to_jpeg_with_color(color))
        if not transparent:
            return result

        width, height = result.size
        alpha = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(alpha)
        columns = width // 16
        for index, record in enumerate(self.records):
            if record is None:
                x = (index % columns) * 16
                y = (index // columns) * 16
                draw.rectangle((x, y, x + 15, y + 15), fill=0)
        result.putalpha(alpha)
        return result

    def describe(self) -> str:
        w, h = RESOLUTIONS[self.resolution]
        lines = [
            trf(
                "受信履歴  {source} -> {destination}  {datetime}",
                source=self.callsign_from,
                destination=self.callsign_to,
                datetime=self.datetime,
            ),
            trf(
                "  解像度: {width}×{height}  画質: {quality} (q{q})",
                width=w,
                height=h,
                quality=tr(QUALITY_NAMES[self.quality]),
                q=QUALITY_Q[self.quality],
            ),
        ]
        if self.missing_count:
            lines.append(
                trf(
                    "  未受信MCU: {missing}/{total}個",
                    missing=self.missing_count,
                    total=len(self.records),
                )
            )
        else:
            lines.append(tr("  未受信なし"))
        return "\n".join(lines)
