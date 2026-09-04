"""表示言語の判定と日本語メッセージの英訳。"""

from __future__ import annotations

import locale
import os
import sys
from typing import Literal

Language = Literal["ja", "en"]

_language: Language | None = None

_ENGLISH: dict[str, str] = {
    "言語にはauto、ja、enのいずれかを指定してください":
        "Language must be auto, ja, or en",
    "自動判定、ja=日本語、en=英語 (既定: auto)":
        "Language: auto-detect, ja=Japanese, en=English (default: auto)",
    "ICOM ID-50の画像用.datファイルを読み書きします。":
        "Read and write ICOM ID-50 image .dat files.",
    "短縮コマンド: -i FILE (info), -d FILE (decode), -e IMAGE (encode)":
        "Short forms: -i FILE (= info FILE), -d FILE (= decode FILE), "
        "-e IMAGE (= encode IMAGE)",
    "ファイル種別と内容を表示する": "Show the file type and metadata",
    ".datファイルをJPEG・PNGへ変換する": "Convert .dat files to JPEG or PNG",
    "出力先フォルダ(既定: カレント)": "Output directory (default: current directory)",
    "出力画像形式: jpg(既定)、png":
        "Output format: jpg (default) or png",
    "受信履歴の未受信MCUの塗りつぶし色(既定: black、transparentはPNGのみ)":
        "Fill for missing RX MCUs (default: black; transparent requires PNG)",
    "送信用.datファイルの指定領域(DAT1〜DAT9)だけを変換する":
        "Decode only one region (1-9) from a transmit .dat file",
    "既存の出力ファイルを上書きする": "Overwrite existing output files",
    "画像から送信用.datファイルを作成する":
        "Create a transmit .dat file from an image",
    "出力ファイル名(既定: 現在時刻のYYYYMMDD_HHMMSS.dat)":
        "Output filename (default: current time as YYYYMMDD_HHMMSS.dat)",
    "アスペクト比4:3への調整方式(既定: pad=余白を黒埋め)":
        "How to fit the image to 4:3 (default: pad with black borders)",
    "GUIを起動する": "Launch the GUI",
    "{path}: 送信用.datファイル (TX Picture Data)":
        "{path}: transmit .dat file (TX Picture Data)",
    "  DAT1〜DAT9およびTHUMを格納  実データサイズ（ゼロパディングを除く合計）: {used:,}バイト":
        "  Contains DAT1-DAT9 and THUM; payload size excluding zero "
        "padding: {used:,} bytes",
    "{path}: IC-705の受信履歴(本ツールでは未対応)":
        "{path}: IC-705 RX history (not supported)",
    "{path}: 対応していないファイル形式です": "{path}: unsupported file",
    "{path}: 読み込みに失敗しました: {error}": "{path}: failed to read: {error}",
    "  {name}  ({width}×{height} {quality} q{q})":
        "  {name}  ({width}x{height} {quality} q{q})",
    "  {name}  (128×96 モノクロ)": "  {name}  (128x96 monochrome)",
    "低画質": "low quality",
    "普通画質": "normal quality",
    "高画質": "high quality",
    "エラー: 出力ファイル名が重複しています":
        "Error: multiple inputs produce the same output filename",
    "エラー: 出力先に同名のファイルが既に存在します (--overwriteで上書き)":
        "Error: output files already exist (use --overwrite to replace them)",
    "{path}: --regionは送信用.datファイルにのみ指定できます":
        "{path}: --region is only valid for transmit .dat files",
    "エラー: --missing transparent はPNG出力でのみ指定できます":
        "Error: --missing transparent requires PNG output",
    "ファイル名にID-50で使用できない文字が含まれています: {name}":
        "The filename contains characters not supported by the ID-50: {name}",
    "拡張子を.datにしてください: {name}":
        "The extension must be .dat: {name}",
    'ファイル名に使用できない文字が含まれています: {name} (\\ / : * ? " < > |)':
        'The filename contains invalid characters: {name} (\\ / : * ? " < > |)',
    "拡張子を除いたファイル名が空です: {name}":
        "The filename has no name part before the extension: {name}",
    "ファイル名の先頭や末尾にスペースやピリオドは使えません: {name}":
        "A filename cannot begin or end with a space or a dot: {name}",
    "ファイル名がWindowsの予約デバイス名です: {name}":
        "The filename is a reserved Windows device name: {name}",
    "ファイル名が長すぎます: {name} ({actual}バイト / 上限{limit}バイト)":
        "Filename is too long: {name} ({actual} bytes; limit is {limit})",
    "ID-50では拡張子を除き半角23文字、全角なら11文字と半角1文字までです。":
        "Excluding the extension, the ID-50 accepts at most 23 single-byte "
        "characters, or 11 double-byte characters plus one single-byte character.",
    "出力先を作成できません: {path}: {error}":
        "Cannot create output directory {path}: {error}",
    "{path}: 変換に失敗しました: {error}": "{path}: conversion failed: {error}",
    "エラー: {error}": "Error: {error}",
    "この画像は1 MCUあたりの符号サイズがレコード上限を超えるため変換できません。":
        "The image cannot be converted because one MCU does not fit in its "
        "record slot.",
    "入力画像を読み込めません: {path}: {error}":
        "Cannot read input image {path}: {error}",
    "出力ファイルを作成できません: {path}: {error}":
        "Cannot create output file {path}: {error}",
    "{path} を作成しました (実データ合計 {total:,}バイト)":
        "Created {path} (total payload: {total:,} bytes)",
    "ID-50 .datファイル": "ID-50 .dat files",
    "すべてのファイル": "All files",
    "画像ファイル": "Image files",
    "ほか {count} 件のファイル": "and {count} more files",
    "既存の{count}ファイルを上書きしますか？\n\n{files}":
        "Overwrite {count} existing files?\n\n{files}",
    ".datファイルを開く": "Open .dat file",
    "ファイルを開いてください。": "Open a file.",
    "解像度:": "Resolution:",
    "画質:": "Quality:",
    "画像を保存": "Save image",
    "全9領域を一括保存": "Save all 9 variants",
    "JPEGとして保存": "Save as JPEG",
    "PNGとして保存": "Save as PNG",
    "THUMをPNGで保存": "Save THUM as PNG",
    "{name}: 送信用.datファイル (DAT1〜DAT9とTHUM)":
        "{name}: transmit .dat file (DAT1-DAT9 and THUM)",
    "プレビューに失敗しました: {error}": "Preview failed: {error}",
    "黒で塗りつぶす": "Fill with black",
    "色を選択...": "Choose color...",
    "透明にする": "Make transparent",
    "未受信部分の色": "Color for missing regions",
    "画像を保存できません: {error}": "Cannot save image: {error}",
    "{path} に10個のファイルを保存しました。": "Saved 10 files to {path}.",
    "THUMを保存できません: {error}": "Cannot save THUM: {error}",
    "画像を開く": "Open image",
    "アスペクト比4:3への調整:": "Fit to 4:3:",
    "余白": "Pad",
    "切り取り": "Crop",
    "引き伸ばし": "Stretch",
    "画像を開いてください。":
        "Open an image to encode as a transmit .dat file.",
    "送信用.datファイルとして保存": "Save as transmit .dat file",
    "画像を開けません: {error}": "Cannot open image: {error}",
    "送信用.datファイルを保存できません: {error}":
        "Cannot save transmit .dat file: {error}",
    "{path} を作成しました。": "Created {path}.",
    "id50dat — ID-50画像.datツール": "id50dat — ID-50 Image .dat Tool",
    "デコード": "Decode",
    "エンコード": "Encode",
    "色名またはRGB値（例: navy, ff8800）を指定してください":
        "Specify a color name or RGB value (for example, navy or ff8800)",
    "RGBの色名またはRGB値を指定してください": "Specify an RGB color name or value",
    "missingには色名、RGB値、またはRGBタプルを指定してください":
        "missing must be a color name, RGB value, or RGB tuple",
    "RGBタプルの各要素は0〜255の整数にしてください":
        "Each RGB tuple component must be an integer from 0 to 255",
    "RGBタプルの各要素は0〜255にしてください":
        "Each RGB tuple component must be from 0 to 255",
    "{ident}領域が見つかりません: {shown!r}":
        "{ident} region not found: {shown!r}",
    "{ident}領域のサイズが不正です":
        "Invalid {ident} region size",
    "送信履歴のファイルサイズが不正です":
        "TX history file size is invalid",
    "受信履歴のファイルサイズが不正です":
        "RX history file size is invalid",
    "ファイル先頭の識別子がID-50ではありません": "File does not start with ID-50",
    "TX Picture History形式のファイルではありません": "File is not TX Picture History",
    "RX Picture History形式のファイルではありません": "File is not RX Picture History",
    "解像度または画質のコードが不正です: {resolution}, {quality}":
        "Invalid resolution or quality code: {resolution}, {quality}",
    "送信履歴  {own} -> {destination}  {datetime}":
        "TX history  {own} -> {destination}  {datetime}",
    "受信履歴  {source} -> {destination}  {datetime}":
        "RX history  {source} -> {destination}  {datetime}",
    "  解像度: {width}×{height}  画質: {quality} (q{q})":
        "  Resolution: {width}x{height}  Quality: {quality} (q{q})",
    "  元ファイル: {source}": "  Source file: {source}",
    "transparentはJPEG出力では指定できません":
        "transparent cannot be used with JPEG output",
    "  未受信MCU: {missing}/{total}個":
        "  Unreceived MCUs: {missing}/{total}",
    "  未受信なし": "  No missing MCUs",
    "レコード{index}のデータ長が不正です: {length}":
        "Invalid data length in record {index}: {length}",
    "MCU {index}の符号長（{length}バイト）が上限（{limit}バイト）を超えています":
        "MCU {index} is {length} bytes, exceeding the {limit}-byte limit",
    "fitにはpad、crop、stretchのいずれかを指定してください: {mode}":
        "fit must be pad, crop, or stretch: {mode}",
    "送信用.datファイルのサイズが不正です":
        "Transmit .dat file size is invalid",
    "TX Picture Data形式のファイルではありません": "File is not TX Picture Data",
    "THUM領域が見つかりません": "THUM region not found",
    "領域{region}が見つかりません (0x{offset:X})":
        "{region} region not found (0x{offset:X})",
    "領域番号は1〜9で指定してください: {region}":
        "Region number must be from 1 to 9: {region}",
    "THUMデータのサイズが不正です":
        "THUM data size is invalid",
    "DAT{region}領域が存在しません": "DAT{region} is missing",
    "DAT{region}のレコード数が不正です: {count}":
        "Invalid record count in DAT{region}: {count}",
    "qは1〜100で指定してください: {q}": "q must be from 1 to 100: {q}",
    "参照JPEGにDQTが見つかりません": "DQT not found in reference JPEG",
    "DHTセグメント数が不正です": "Invalid DHT segment count",
    "MCU数が一致しません": "MCU count mismatch",
    "マーカーの位置が不正です: offset 0x{offset:X}":
        "Invalid marker position at offset 0x{offset:X}",
    "SOSが見つかりません": "SOS marker not found",
    "想定外のマーカーです: FF{marker:02X} (offset 0x{offset:X})":
        "Unexpected marker FF{marker:02X} at offset 0x{offset:X}",
    "EOIが見つかりません": "EOI marker not found",
    "幅と高さは16の倍数にしてください: {width}×{height}":
        "Width and height must be multiples of 16: {width}x{height}",
    "MCU {index}の符号長（{length}バイト）が上限（{limit}バイト）を超えています":
        "MCU {index} is {length} bytes, exceeding its {limit}-byte record slot",
    "THUMデータのサイズが不正です":
        "THUM data size is invalid",
    "THUM画像の解像度が不正です":
        "THUM resolution is invalid",
    "出力画像形式にはjpgまたはpngを指定してください":
        "Output format must be jpg or png",
    "IC-705の受信履歴には対応していません: {path}":
        "IC-705 RX history is not supported: {path}",
    "対応していないファイル形式です: {path}": "Unsupported file: {path}",
}


def _normalize_language(value: str | None) -> Language | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized == "auto":
        return None
    if normalized.startswith("ja") or normalized.startswith("japanese"):
        return "ja"
    if normalized.startswith("en") or normalized.startswith("english"):
        return "en"
    return None


def _windows_ui_language() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(lang_id)
    except (AttributeError, OSError):
        return None


def detect_language() -> Language:
    """明示設定とOSの言語設定から表示言語を判定する。"""
    configured = os.environ.get("ID50DAT_LANG")
    if configured:
        language = _normalize_language(configured)
        if language:
            return language

    windows_language = _normalize_language(_windows_ui_language())
    if windows_language:
        return windows_language

    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "").split(":", 1)[0]
        language = _normalize_language(value)
        if language:
            return language

    language = _normalize_language(locale.getlocale()[0])
    return language or "en"


def set_language(language: str = "auto") -> None:
    """表示言語を設定する。autoはOS設定から判定する。"""
    global _language
    if language == "auto":
        _language = detect_language()
        return
    normalized = _normalize_language(language)
    if normalized is None:
        raise ValueError(tr("言語にはauto、ja、enのいずれかを指定してください"))
    _language = normalized


def get_language() -> Language:
    """現在の表示言語を返す。"""
    global _language
    if _language is None:
        _language = detect_language()
    return _language


def tr(message: str) -> str:
    """日本語の原文を現在の表示言語へ翻訳する。"""
    if get_language() == "en":
        return _ENGLISH.get(message, message)
    return message


def trf(message: str, /, **values) -> str:
    """翻訳後のメッセージへ値を埋め込む。"""
    return tr(message).format(**values)
