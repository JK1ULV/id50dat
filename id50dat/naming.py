"""出力ファイル名の生成と、.datファイル名の検査。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import (
    FILENAME_ENCODING,
    FILENAME_MAX_BYTES,
    QUALITY_SLUGS,
    REGIONS,
    RESOLUTIONS,
)
from .i18n import tr, trf

if TYPE_CHECKING:
    from .history import RxHistory, TxHistory

__all__ = [
    "dat_filename_fits",
    "dat_filename_length",
    "dat_filename_message",
    "dat_filename_problem",
    "history_image_name",
    "history_thumbnail_name",
    "normalize_image_format",
    "tx_data_image_name",
    "tx_data_thumbnail_name",
]


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DATETIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def dat_filename_length(path) -> int | None:
    """.datファイル名の、拡張子を除いた部分のCP932でのバイト数を返す。

    CP932で表せない文字を含む場合はNoneを返す。上限はFILENAME_MAX_BYTESである。
    """
    return _stem_length(Path(path).stem)


def _stem_length(stem: str) -> int | None:
    try:
        return len(stem.encode(FILENAME_ENCODING))
    except UnicodeEncodeError:
        return None


def dat_filename_problem(path) -> str | None:
    """ID-50が扱えない.datファイル名なら、その理由の種別を返す。

    戻り値:
        "extension" .dat以外の拡張子、または拡張子がない
        "chars"     WindowsおよびFATで使用できない文字を含む
        "empty"     拡張子を除いた部分が空
        "edge"      先頭または末尾が空白かドット
        "reserved"  Windowsの予約名
        "encoding"  CP932で表せない文字を含む
        "length"    拡張子を除いた部分がFILENAME_MAX_BYTESを超える
        None        問題なし
    """
    filename = Path(path).name
    if not filename.lower().endswith(".dat"):
        return "extension"
    stem = filename[:-4]
    if _INVALID_FILENAME_CHARS.search(stem):
        return "chars"
    if not stem:
        return "empty"
    # Windowsは末尾のスペースやピリオドを自動的に除去するため、ファイル名が変わってしまう。
    if stem[0] in " ." or stem[-1] in " .":
        return "edge"
    reserved_candidate = stem.split(".", 1)[0].rstrip(" .").upper()
    if reserved_candidate in _WINDOWS_RESERVED_NAMES:
        return "reserved"
    length = _stem_length(stem)
    if length is None:
        return "encoding"
    if length > FILENAME_MAX_BYTES:
        return "length"
    return None


def dat_filename_fits(path) -> bool:
    """ID-50が扱える.datファイル名かどうかを返す。"""
    return dat_filename_problem(path) is None


def dat_filename_message(path, problem: str | None = None) -> str:
    """dat_filename_problem()の理由を、表示用の文言にして返す。"""
    if problem is None:
        problem = dat_filename_problem(path)
    name = Path(path).name
    if problem == "extension":
        return trf("拡張子を.datにしてください: {name}", name=name)
    if problem == "chars":
        return trf(
            'ファイル名に使用できない文字が含まれています: {name} (\\ / : * ? " < > |)',
            name=name,
        )
    if problem == "empty":
        return trf("拡張子を除いたファイル名が空です: {name}", name=name)
    if problem == "edge":
        return trf(
            "ファイル名の先頭や末尾にスペースやピリオドは使えません: {name}", name=name
        )
    if problem == "reserved":
        return trf("ファイル名がWindowsの予約デバイス名です: {name}", name=name)
    if problem == "encoding":
        return trf("ファイル名にID-50で使用できない文字が含まれています: {name}", name=name)
    if problem == "length":
        return trf(
            "ファイル名が長すぎます: {name} ({actual}バイト / 上限{limit}バイト)",
            name=name,
            actual=dat_filename_length(path),
            limit=FILENAME_MAX_BYTES,
        ) + "\n" + tr(
            "ID-50では拡張子を除き半角23文字、全角なら11文字と半角1文字までです。"
        )
    return ""


def _component(value: str, fallback: str) -> str:
    """Windowsで安全なファイル名の構成要素へ変換する。"""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    if cleaned.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned or fallback


def _datetime_component(value: str) -> str | None:
    match = _DATETIME.fullmatch(value)
    if not match:
        return None
    return "".join(match.groups()[:3]) + "_" + "".join(match.groups()[3:])


def _image_suffix(resolution: int, quality: int, image_format: str) -> str:
    width, height = RESOLUTIONS[resolution]
    image_format = normalize_image_format(image_format)
    return f"{width}x{height}_{QUALITY_SLUGS[quality]}.{image_format}"


def normalize_image_format(value: str) -> str:
    """出力画像形式を正規化する。jpegはjpgの別名として扱う。"""
    normalized = value.lower()
    if normalized == "jpeg":
        return "jpg"
    if normalized in ("jpg", "png"):
        return normalized
    raise ValueError(tr("出力画像形式にはjpgまたはpngを指定してください"))


def tx_data_image_name(input_stem: str, region: int, image_format: str) -> str:
    """送信用.datの指定領域の出力ファイル名を返す。"""
    _offset, _count, resolution, quality = REGIONS[region]
    stem = _component(input_stem, "image")
    return f"{stem}_{_image_suffix(resolution, quality, image_format)}"


def tx_data_thumbnail_name(input_stem: str) -> str:
    """送信用.datのTHUM出力ファイル名を返す。"""
    return f"{_component(input_stem, 'image')}_thum.png"


def _tx_history_stem(history: TxHistory, fallback_stem: str) -> str:
    # 同じ送信用ファイルを繰り返し送信した履歴とTHUMを区別できるよう、
    # 受信履歴と同じく日時を先頭に置き、時系列にも並べる。
    base = _datetime_component(history.datetime) or _component(
        fallback_stem, "tx_history"
    )
    source_stem = Path(history.source_name).stem if history.source_name else ""
    source = _component(source_stem, "") if source_stem else ""
    own = _component(history.callsign_own, "unknown")
    to = _component(history.callsign_to, "unknown")
    parts = [base, source] if source else [base]
    return "_".join([*parts, own, "to", to])


def _rx_history_stem(history: RxHistory, fallback_stem: str) -> str:
    base = _datetime_component(history.datetime) or _component(
        fallback_stem, "rx_history"
    )
    source = _component(history.callsign_from, "unknown")
    to = _component(history.callsign_to, "unknown")
    return f"{base}_{source}_to_{to}"


def history_image_name(
    history: TxHistory | RxHistory, fallback_stem: str, image_format: str
) -> str:
    """送受信履歴の出力ファイル名を返す。"""
    if history.kind == "tx_history":
        stem = _tx_history_stem(history, fallback_stem)
    else:
        stem = _rx_history_stem(history, fallback_stem)
    return f"{stem}_{_image_suffix(history.resolution, history.quality, image_format)}"


def history_thumbnail_name(history: TxHistory, fallback_stem: str) -> str:
    """送信履歴のTHUM出力ファイル名を返す。"""
    return f"{_tx_history_stem(history, fallback_stem)}_thum.png"
