"""id50datのコマンドラインインターフェース。"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import RxHistory, TxHistory, TxPictureData, detect, load
from .constants import (
    QUALITY_NAMES,
    QUALITY_Q,
    REGIONS,
    RESOLUTIONS,
)
from .history import resolve_missing
from .i18n import set_language, tr, trf
from .jpegio import RecordTooLargeError
from .naming import (
    dat_filename_message,
    dat_filename_problem,
    history_image_name,
    history_thumbnail_name,
    normalize_image_format,
    tx_data_image_name,
    tx_data_thumbnail_name,
)

_SHORTCUT_COMMANDS = {
    "-i": "info",
    "-d": "decode",
    "-e": "encode",
}


@dataclass
class _DecodeItem:
    path: str
    stem: str
    obj: TxPictureData | TxHistory | RxHistory
    outputs: list[Path]


def _parse_missing(value: str):
    """argparse向けに未受信MCUの塗りつぶし方法を解釈する。"""
    try:
        return resolve_missing(value)
    except (TypeError, ValueError) as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def _parse_image_format(value: str) -> str:
    """argparse向けに出力画像形式を正規化する。"""
    try:
        return normalize_image_format(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def _normalize_command_shortcut(argv: list[str]) -> list[str]:
    """先頭の短縮指定を既存のサブコマンドへ置き換える。"""
    command_index = 0
    if argv[:1] == ["--lang"] and len(argv) >= 3:
        command_index = 2
    elif argv[:1] and argv[0].startswith("--lang="):
        command_index = 1
    if len(argv) > command_index and argv[command_index] in _SHORTCUT_COMMANDS:
        normalized = list(argv)
        normalized[command_index] = _SHORTCUT_COMMANDS[argv[command_index]]
        return normalized
    return argv


def _language_option(argv: list[str]) -> str:
    """完全な引数解析より先に表示言語の指定を取り出す。"""
    if "--lang" in argv:
        index = argv.index("--lang")
        if index + 1 < len(argv) and argv[index + 1] in ("auto", "ja", "en"):
            return argv[index + 1]
    for argument in argv:
        if argument.startswith("--lang="):
            value = argument.partition("=")[2]
            if value in ("auto", "ja", "en"):
                return value
    return "auto"


def _expand_input_patterns(paths: list[str]) -> list[str]:
    """シェルが展開しない入力ファイルのワイルドカードを展開する。"""
    expanded: list[str] = []
    for path in paths:
        if "*" not in path and "?" not in path:
            expanded.append(path)
            continue
        matches = sorted(glob.glob(path))
        expanded.extend(matches or [path])
    return expanded


def _cmd_info(args: argparse.Namespace) -> int:
    status = 0
    for path in _expand_input_patterns(args.files):
        try:
            kind = detect(path)
            if kind == "tx_dat":
                obj = TxPictureData.load(path)
                used = sum(len(m) for recs in obj.regions.values() for m in recs)
                print(
                    trf("{path}: 送信用.datファイル (TX Picture Data)", path=path)
                )
                print(
                    trf(
                        "  DAT1〜DAT9およびTHUMを格納  "
                        "実データサイズ（ゼロパディングを除く合計）: {used:,}バイト",
                        used=used,
                    )
                )
            elif kind in ("tx_history", "rx_history"):
                obj = load(path)
                print(f"{path}:")
                for line in obj.describe().splitlines():
                    print(f"  {line}")
            elif kind == "ic705_rx_history":
                print(trf(
                    "{path}: IC-705の受信履歴(本ツールでは未対応)", path=path
                ))
            else:
                print(trf("{path}: 対応していないファイル形式です", path=path))
                status = 1
        except (OSError, ValueError) as e:
            print(
                trf("{path}: 読み込みに失敗しました: {error}", path=path, error=e),
                file=sys.stderr,
            )
            status = 1
    return status


def _decode_tx_dat(
    obj: TxPictureData, stem: str, outdir: Path, region, image_format: str
) -> None:
    targets = [region] if region else list(REGIONS)
    for n in targets:
        _off, _cnt, res, qual = REGIONS[n]
        w, h = RESOLUTIONS[res]
        name = tx_data_image_name(stem, n, image_format)
        output_path = outdir / name
        if image_format == "jpg":
            output_path.write_bytes(obj.region_jpeg(n))
        else:
            obj.region_image(n).save(output_path, format="PNG")
        print(
            trf(
                "  {name}  ({width}×{height} {quality} q{q})",
                name=name,
                width=w,
                height=h,
                quality=tr(QUALITY_NAMES[qual]),
                q=QUALITY_Q[qual],
            )
        )
    if not region:
        thum_name = tx_data_thumbnail_name(stem)
        obj.thum_image().save(outdir / thum_name)
        print(trf("  {name}  (128×96 モノクロ)", name=thum_name))


def _tx_dat_output_paths(
    stem: str, outdir: Path, region: int | None, image_format: str
) -> list[Path]:
    targets = [region] if region else list(REGIONS)
    paths = [outdir / tx_data_image_name(stem, n, image_format) for n in targets]
    if not region:
        paths.append(outdir / tx_data_thumbnail_name(stem))
    return paths


def _history_output_paths(
    obj: TxHistory | RxHistory, stem: str, outdir: Path, image_format: str
) -> list[Path]:
    paths = [outdir / history_image_name(obj, stem, image_format)]
    if isinstance(obj, TxHistory):
        paths.append(outdir / history_thumbnail_name(obj, stem))
    return paths


def _output_key(path: Path) -> str:
    key = str(path.resolve())
    return key.casefold() if os.name == "nt" else key


def _check_output_paths(paths: list[Path], overwrite: bool) -> bool:
    seen: dict[str, Path] = {}
    duplicate_paths: list[Path] = []
    for path in paths:
        key = _output_key(path)
        if key in seen:
            duplicate_paths.append(path)
        else:
            seen[key] = path
    if duplicate_paths:
        print(tr("エラー: 出力ファイル名が重複しています"), file=sys.stderr)
        for path in duplicate_paths:
            print(f"  {path}", file=sys.stderr)
        return False

    existing_paths = [path for path in paths if path.exists()]
    if existing_paths and not overwrite:
        print(
            tr("エラー: 出力先に同名のファイルが既に存在します (--overwriteで上書き)"),
            file=sys.stderr,
        )
        for path in existing_paths:
            print(f"  {path}", file=sys.stderr)
        return False
    return True


def _cmd_decode(args: argparse.Namespace) -> int:
    status = 0
    items: list[_DecodeItem] = []
    for path in _expand_input_patterns(args.files):
        stem = Path(path).stem
        try:
            obj = load(path)
        except (OSError, ValueError) as e:
            print(f"{path}: {e}", file=sys.stderr)
            status = 1
            continue
        if isinstance(obj, TxPictureData):
            outputs = _tx_dat_output_paths(
                stem, Path(args.output), args.region, args.image_format
            )
        else:
            outputs = _history_output_paths(
                obj, stem, Path(args.output), args.image_format
            )
        items.append(_DecodeItem(path=path, stem=stem, obj=obj, outputs=outputs))

    if not items:
        return status

    invalid_options = False
    if args.region is not None:
        for item in items:
            if not isinstance(item.obj, TxPictureData):
                print(
                    trf(
                        "{path}: --regionは送信用.datファイルにのみ指定できます",
                        path=item.path,
                    ),
                    file=sys.stderr,
                )
                invalid_options = True
    if invalid_options:
        return 2
    if args.missing == "transparent" and args.image_format != "png":
        print(
            tr("エラー: --missing transparent はPNG出力でのみ指定できます"),
            file=sys.stderr,
        )
        return 2

    missing = args.missing if args.missing is not None else (0, 0, 0)

    outdir = Path(args.output)
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(
            trf("出力先を作成できません: {path}: {error}", path=outdir, error=e),
            file=sys.stderr,
        )
        return 1
    if not _check_output_paths(
        [output for item in items for output in item.outputs], args.overwrite
    ):
        return 1

    for item in items:
        path, stem, obj = item.path, item.stem, item.obj
        print(f"{path}:")
        try:
            if isinstance(obj, TxPictureData):
                _decode_tx_dat(obj, stem, outdir, args.region, args.image_format)
            elif isinstance(obj, (TxHistory, RxHistory)):
                for line in obj.describe().splitlines():
                    print(f"  {line}")
                name = history_image_name(obj, stem, args.image_format)
                output_path = outdir / name
                if args.image_format == "png":
                    image = (
                        obj.to_image(missing)
                        if isinstance(obj, RxHistory)
                        else obj.to_image()
                    )
                    image.save(output_path, format="PNG")
                else:
                    jpeg = (
                        obj.to_jpeg(missing=missing)
                        if isinstance(obj, RxHistory)
                        else obj.to_jpeg()
                    )
                    output_path.write_bytes(jpeg)
                print(f"  {name}")
                if isinstance(obj, TxHistory):
                    thum_name = history_thumbnail_name(obj, stem)
                    obj.thum_image().save(outdir / thum_name)
                    print(f"  {thum_name}")
        except (OSError, ValueError) as e:
            print(
                trf("{path}: 変換に失敗しました: {error}", path=path, error=e),
                file=sys.stderr,
            )
            status = 1
    return status


def _check_dat_filename(path: Path) -> bool:
    """ID-50の仕様に適合しない.datファイル名なら理由を表示してFalseを返す。"""
    problem = dat_filename_problem(path)
    if problem is None:
        return True
    print(
        trf("エラー: {error}", error=dat_filename_message(path, problem)),
        file=sys.stderr,
    )
    return False


def _cmd_encode(args: argparse.Namespace) -> int:
    from PIL import Image

    out = args.output
    if out is None:
        out = datetime.now().strftime("%Y%m%d_%H%M%S") + ".dat"
    output_path = Path(out)
    if not _check_dat_filename(output_path):
        return 2
    if output_path.exists() and not args.overwrite:
        print(
            tr("エラー: 出力先に同名のファイルが既に存在します (--overwriteで上書き)"),
            file=sys.stderr,
        )
        print(f"  {output_path}", file=sys.stderr)
        return 1
    try:
        with Image.open(args.image) as img:
            dat = TxPictureData.from_image(img, fit=args.fit)
    except RecordTooLargeError as e:
        print(trf("エラー: {error}", error=e), file=sys.stderr)
        print(
            tr("この画像は1 MCUあたりの符号サイズがレコード上限を超えるため変換できません。"),
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as e:
        print(
            trf("入力画像を読み込めません: {path}: {error}", path=args.image, error=e),
            file=sys.stderr,
        )
        return 1
    try:
        dat.save(output_path)
    except (OSError, ValueError) as e:
        print(
            trf(
                "出力ファイルを作成できません: {path}: {error}",
                path=output_path,
                error=e,
            ),
            file=sys.stderr,
        )
        return 1
    total = sum(len(m) for recs in dat.regions.values() for m in recs)
    print(
        trf(
            "{path} を作成しました (実データ合計 {total:,}バイト)",
            path=output_path,
            total=total,
        )
    )
    return 0


def _cmd_gui(_args: argparse.Namespace) -> int:
    from .gui import run

    run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="id50dat",
        description=tr("ICOM ID-50の画像用.datファイルを読み書きします。"),
        epilog=tr(
            "短縮コマンド: -i FILE (info), -d FILE (decode), "
            "-e IMAGE (encode)"
        ),
    )
    parser.add_argument(
        "--lang",
        choices=("auto", "ja", "en"),
        default="auto",
        help=tr("自動判定、ja=日本語、en=英語 (既定: auto)"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help=tr("ファイル種別と内容を表示する"))
    p.add_argument("files", nargs="+", metavar="FILE")
    p.set_defaults(func=_cmd_info)

    p = sub.add_parser("decode", help=tr(".datファイルをJPEG・PNGへ変換する"))
    p.add_argument("files", nargs="+", metavar="FILE")
    p.add_argument(
        "-o", "--output", default=".", help=tr("出力先フォルダ(既定: カレント)")
    )
    p.add_argument(
        "-f",
        "--format",
        dest="image_format",
        type=_parse_image_format,
        metavar="FORMAT",
        default="jpg",
        help=tr("出力画像形式: jpg(既定)、png"),
    )
    p.add_argument(
        "--missing",
        type=_parse_missing,
        metavar="COLOR",
        default=None,
        help=tr("受信履歴の未受信MCUの塗りつぶし色(既定: black、transparentはPNGのみ)"),
    )
    p.add_argument(
        "--region",
        type=int,
        choices=range(1, 10),
        metavar="N",
        help=tr("送信用.datファイルの指定領域(DAT1〜DAT9)だけを変換する"),
    )
    p.add_argument(
        "--overwrite", action="store_true", help=tr("既存の出力ファイルを上書きする")
    )
    p.set_defaults(func=_cmd_decode)

    p = sub.add_parser("encode", help=tr("画像から送信用.datファイルを作成する"))
    p.add_argument("image", metavar="IMAGE")
    p.add_argument(
        "-o",
        "--output",
        help=tr("出力ファイル名(既定: 現在時刻のYYYYMMDD_HHMMSS.dat)"),
    )
    p.add_argument(
        "--fit",
        choices=("pad", "crop", "stretch"),
        default="pad",
        help=tr("アスペクト比4:3への調整方式(既定: pad=余白を黒埋め)"),
    )
    p.add_argument(
        "--overwrite", action="store_true", help=tr("既存の出力ファイルを上書きする")
    )
    p.set_defaults(func=_cmd_encode)

    p = sub.add_parser("gui", help=tr("GUIを起動する"))
    p.set_defaults(func=_cmd_gui)

    return parser


def main(argv=None) -> int:
    command_argv = sys.argv[1:] if argv is None else list(argv)
    set_language(_language_option(command_argv))
    args = build_parser().parse_args(_normalize_command_shortcut(command_argv))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
