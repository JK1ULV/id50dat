"""送信用.datファイル(TX Picture Data)の読み書き。"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from . import jpegio, naming, thum
from .constants import (
    ENCODE_HEIGHTS,
    MAGIC,
    QUALITY_Q,
    RECORD_SIZE,
    RECORD_SLOT,
    REGIONS,
    RESOLUTIONS,
    THUM_OFFSET,
    THUM_PAYLOAD_SIZE,
    TX_DAT_SIZE,
    TYPE_OFFSET,
    TYPE_TX_DAT,
    VERSION,
    VERSION_OFFSET,
)
from .i18n import tr, trf

__all__ = ["TxPictureData", "fit_image", "read_records", "pack_records"]


def read_records(data: bytes, offset: int, count: int) -> list[bytes]:
    """386バイトレコードの列を読み取り、実データのリストを返す。"""
    records = []
    for i in range(count):
        base = offset + i * RECORD_SIZE
        length = int.from_bytes(data[base : base + 2], "little")
        if length > RECORD_SLOT:
            raise ValueError(trf(
                "レコード{index}のデータ長が不正です: {length}",
                index=i,
                length=length,
            ))
        records.append(bytes(data[base + 2 : base + 2 + length]))
    return records


def pack_records(mcus: list[bytes]) -> bytes:
    """MCU符号のリストを386バイトレコード列へ格納する。"""
    out = bytearray()
    for i, mcu in enumerate(mcus):
        if len(mcu) > RECORD_SLOT:
            raise jpegio.RecordTooLargeError(trf(
                "MCU {index}の符号長（{length}バイト）が上限（{limit}バイト）を超えています",
                index=i,
                length=len(mcu),
                limit=RECORD_SLOT,
            ))
        out += len(mcu).to_bytes(2, "little")
        out += mcu
        out += b"\x00" * (RECORD_SLOT - len(mcu))
    return bytes(out)


def fit_image(image: Image.Image, size: tuple[int, int], mode: str) -> Image.Image:
    """画像を指定サイズへ合わせる。

    mode:
        pad     縦横比を保って収め、余白を黒で埋める(既定)
        crop    縦横比を保って覆い、はみ出しを中央で切り取る
        stretch 縦横比を無視して引き伸ばす
    """
    tw, th = size
    src = image.convert("RGB")
    if mode == "stretch":
        return src.resize(size, Image.Resampling.LANCZOS)
    if mode not in ("pad", "crop"):
        raise ValueError(trf(
            "fitにはpad、crop、stretchのいずれかを指定してください: {mode}", mode=mode
        ))
    scale_fn = min if mode == "pad" else max
    scale = scale_fn(tw / src.width, th / src.height)
    nw = max(1, round(src.width * scale))
    nh = max(1, round(src.height * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    if mode == "pad":
        canvas = Image.new("RGB", size, (0, 0, 0))
        canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        return canvas
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


@dataclass
class TxPictureData:
    """送信用.datファイルの内容。"""

    thum: bytes                              # 1,536バイトのTHUMペイロード
    regions: dict[int, list[bytes]] = field(default_factory=dict)  # 1〜9

    kind = "tx_dat"

    # ------------------------------------------------------------------
    # 読み取り
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, data: bytes) -> "TxPictureData":
        if len(data) != TX_DAT_SIZE:
            raise ValueError(tr("送信用.datファイルのサイズが不正です"))
        if not data.startswith(MAGIC):
            raise ValueError(tr("ファイル先頭の識別子がID-50ではありません"))
        if data[TYPE_OFFSET : TYPE_OFFSET + len(TYPE_TX_DAT)] != TYPE_TX_DAT:
            raise ValueError(tr("TX Picture Data形式のファイルではありません"))
        if data[THUM_OFFSET : THUM_OFFSET + 4] != b"THUM":
            raise ValueError(tr("THUM領域が見つかりません"))
        thum_payload = bytes(
            data[THUM_OFFSET + 4 : THUM_OFFSET + 4 + THUM_PAYLOAD_SIZE]
        )
        regions: dict[int, list[bytes]] = {}
        for n, (offset, count, _res, _qual) in REGIONS.items():
            ident = f"DAT{n}".encode()
            if data[offset : offset + 4] != ident:
                raise ValueError(trf(
                    "領域{region}が見つかりません (0x{offset:X})",
                    region=ident.decode(),
                    offset=offset,
                ))
            regions[n] = read_records(data, offset + 4, count)
        return cls(thum=thum_payload, regions=regions)

    @classmethod
    def load(cls, path) -> "TxPictureData":
        with open(path, "rb") as f:
            return cls.parse(f.read())

    # ------------------------------------------------------------------
    # 変換
    # ------------------------------------------------------------------

    def region_jpeg(self, n: int) -> bytes:
        """領域番号(1〜9)のレコードからJPEGを構成する。"""
        if n not in REGIONS:
            raise ValueError(trf("領域番号は1〜9で指定してください: {region}", region=n))
        _offset, _count, res, qual = REGIONS[n]
        width, height = RESOLUTIONS[res]  # SOF0の高さは表示上の高さでよい
        return jpegio.build_jpeg(self.regions[n], width, height, QUALITY_Q[qual])

    def region_image(self, n: int) -> Image.Image:
        """領域番号(1〜9)をRGBのPillow画像として返す。"""
        return jpegio.decode_jpeg(self.region_jpeg(n))

    def thum_image(self) -> Image.Image:
        return thum.decode_thum(self.thum)

    # ------------------------------------------------------------------
    # 作成
    # ------------------------------------------------------------------

    @classmethod
    def from_image(cls, image: Image.Image, fit: str = "pad") -> "TxPictureData":
        """カラー画像から送信用.datファイルの内容を生成する。"""
        regions: dict[int, list[bytes]] = {}
        base_640 = None
        for n, (_offset, _count, res, qual) in REGIONS.items():
            width, _display_h = RESOLUTIONS[res]
            enc_h = ENCODE_HEIGHTS[res]
            fitted = fit_image(image, RESOLUTIONS[res], fit)
            if res == 2 and base_640 is None:
                base_640 = fitted
            if enc_h != fitted.height:  # 160×120 -> 160×128(末尾8行は黒)
                canvas = Image.new("RGB", (width, enc_h), (0, 0, 0))
                canvas.paste(fitted, (0, 0))
                fitted = canvas
            regions[n] = jpegio.encode_mcus(fitted, QUALITY_Q[qual])
        if base_640 is None:
            base_640 = fit_image(image, RESOLUTIONS[2], fit)
        return cls(thum=thum.make_thum(base_640), regions=regions)

    def to_bytes(self) -> bytes:
        """送信用.datファイル全体(1,831,280バイト)を組み立てる。"""
        if len(self.thum) != THUM_PAYLOAD_SIZE:
            raise ValueError(tr("THUMデータのサイズが不正です"))
        out = bytearray(TX_DAT_SIZE)
        out[0 : len(MAGIC)] = MAGIC
        out[TYPE_OFFSET : TYPE_OFFSET + len(TYPE_TX_DAT)] = TYPE_TX_DAT
        out[VERSION_OFFSET : VERSION_OFFSET + len(VERSION)] = VERSION
        out[THUM_OFFSET : THUM_OFFSET + 4] = b"THUM"
        out[THUM_OFFSET + 4 : THUM_OFFSET + 4 + THUM_PAYLOAD_SIZE] = self.thum
        for n, (offset, count, _res, _qual) in REGIONS.items():
            try:
                mcus = self.regions[n]
            except KeyError as e:
                raise ValueError(trf("DAT{region}領域が存在しません", region=n)) from e
            if len(mcus) != count:
                raise ValueError(trf(
                    "DAT{region}のレコード数が不正です: {count}",
                    region=n,
                    count=len(mcus),
                ))
            out[offset : offset + 4] = f"DAT{n}".encode()
            packed = pack_records(mcus)
            out[offset + 4 : offset + 4 + len(packed)] = packed
        return bytes(out)

    def save(self, path) -> None:
        """ID-50の命名仕様に適合するファイル名で送信用.datファイルを保存する。

        ファイル名が本体の制約に反する場合はValueErrorを送出し、書き込まない。
        検査を通さずに書きたい場合はto_bytes()の結果を直接保存する。
        """
        problem = naming.dat_filename_problem(path)
        if problem is not None:
            raise ValueError(naming.dat_filename_message(path, problem))
        data = self.to_bytes()
        with open(path, "wb") as f:
            f.write(data)
