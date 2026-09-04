"""ICOM ID-50の画像用.datファイルを読み書きするライブラリ。"""

from __future__ import annotations

import os

from .constants import (
    MAGIC,
    RX_HISTORY_SIZE,
    TX_DAT_SIZE,
    TX_HISTORY_SIZE,
    TYPE_OFFSET,
    TYPE_RX_HISTORY,
    TYPE_TX_DAT,
    TYPE_TX_HISTORY,
)
from .history import RxHistory, TxHistory
from .i18n import get_language, set_language, trf
from .jpegio import RecordTooLargeError
from .naming import (
    dat_filename_fits,
    dat_filename_message,
    dat_filename_problem,
    history_image_name,
    history_thumbnail_name,
    tx_data_image_name,
    tx_data_thumbnail_name,
)
from .thum import decode_thum, encode_thum, make_thum
from .txdat import TxPictureData

__version__ = "0.1.0"
__all__ = [
    "TxPictureData",
    "dat_filename_fits",
    "dat_filename_message",
    "dat_filename_problem",
    "TxHistory",
    "RxHistory",
    "history_image_name",
    "history_thumbnail_name",
    "tx_data_image_name",
    "tx_data_thumbnail_name",
    "RecordTooLargeError",
    "detect",
    "load",
    "decode_thum",
    "encode_thum",
    "make_thum",
    "get_language",
    "set_language",
    "__version__",
]


def detect(path) -> str:
    """ファイル種別を判定する。

    戻り値: "tx_dat" | "tx_history" | "rx_history" | "ic705_rx_history" | "unknown"
    """
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(0x40)
    type_field = head[TYPE_OFFSET:0x30]
    if head.startswith(MAGIC):
        if type_field.startswith(TYPE_TX_DAT) and size == TX_DAT_SIZE:
            return "tx_dat"
        if type_field.startswith(TYPE_TX_HISTORY) and size == TX_HISTORY_SIZE:
            return "tx_history"
        if type_field.startswith(TYPE_RX_HISTORY) and size == RX_HISTORY_SIZE:
            return "rx_history"
    if head.startswith(b"IC-705") and type_field.startswith(TYPE_RX_HISTORY):
        return "ic705_rx_history"
    return "unknown"


def load(path):
    """.datファイルを種別に応じて読み込む。

    戻り値: TxPictureData | TxHistory | RxHistory
    """
    kind = detect(path)
    if kind == "tx_dat":
        return TxPictureData.load(path)
    if kind == "tx_history":
        return TxHistory.load(path)
    if kind == "rx_history":
        return RxHistory.load(path)
    if kind == "ic705_rx_history":
        raise ValueError(trf("IC-705の受信履歴には対応していません: {path}", path=path))
    raise ValueError(trf("対応していないファイル形式です: {path}", path=path))
