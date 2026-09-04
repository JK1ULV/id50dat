"""ID-50画像用.datファイルの解析結果に基づく構造定数。"""

# ---------------------------------------------------------------------------
# ファイル種別の識別
# ---------------------------------------------------------------------------

MAGIC = b"ID-50"
TYPE_OFFSET = 0x10
TYPE_TX_DAT = b"TX Picture Data"
TYPE_TX_HISTORY = b"TX Picture History"
TYPE_RX_HISTORY = b"RX Picture History"
VERSION_OFFSET = 0x34
VERSION = b"1.05-000"

TX_DAT_SIZE = 1_831_280
TX_HISTORY_SIZE = 465_408
RX_HISTORY_SIZE = 463_872

# ---------------------------------------------------------------------------
# レコード
# ---------------------------------------------------------------------------

RECORD_SIZE = 386   # 2バイトの実データ長ヘッダー + 384バイトのMCU符号スロット
RECORD_SLOT = 384   # 1 MCU分のエントロピー符号の最大長

# ---------------------------------------------------------------------------
# ファイル名の制約
#
# 取扱説明書のファイル名の上限は「半角23字、全角の場合は11字と半角1字」
# (いずれも拡張子を除く)で、Windows-31J(CP932)に直すとどちらも
# 23バイトである。
# ".dat"とNUL終端を加えても28バイトとなり、送信履歴が元ファイル名を保持する
# 32バイトの領域に収まる。上限を超える名前は本体側で正しく扱えないため、
# エンコード時に出力ファイル名を検査する。
# ---------------------------------------------------------------------------

FILENAME_ENCODING = "cp932"   # ファイル名はWindows-31Jで格納される
FILENAME_MAX_BYTES = 23       # 拡張子を除いた部分の上限

# ---------------------------------------------------------------------------
# 解像度と画質
# ---------------------------------------------------------------------------

# 解像度コード(履歴の0x6C / 0x90)および画質コード(0x6D / 0x91)
RESOLUTIONS = {0: (160, 120), 1: (320, 240), 2: (640, 480)}
QUALITY_Q = {0: 25, 1: 48, 2: 75}          # libjpegの品質値(ST-ID50W準拠)
QUALITY_NAMES = {0: "低画質", 1: "普通画質", 2: "高画質"}
QUALITY_SLUGS = {0: "low", 1: "normal", 2: "high"}

# 160×120は内部で160×128として符号化される(末尾8行は黒)。
# JPEGとして出力する際のSOF0の高さは120でよい。
ENCODE_HEIGHTS = {0: 128, 1: 240, 2: 480}


def mcu_count(res_index: int) -> int:
    """解像度コードに対応するMCU数(=使用レコード数)を返す。"""
    width, _ = RESOLUTIONS[res_index]
    return width * ENCODE_HEIGHTS[res_index] // 256


# ---------------------------------------------------------------------------
# 送信用.datファイル(TX Picture Data)のレイアウト
# ---------------------------------------------------------------------------

THUM_OFFSET = 0x40          # b"THUM" + 1,536バイトの二値画像
THUM_PAYLOAD_SIZE = 1536    # 128×96画素、1画素1ビット
THUM_WIDTH = 128
THUM_HEIGHT = 96

# 領域番号 -> (開始位置, レコード数, 解像度コード, 画質コード)
REGIONS = {
    1: (0x000644, 80, 0, 0),
    2: (0x007EE8, 80, 0, 1),
    3: (0x00F78C, 80, 0, 2),
    4: (0x017030, 300, 1, 0),
    5: (0x03348C, 300, 1, 1),
    6: (0x04F8E8, 300, 1, 2),
    7: (0x06BD44, 1200, 2, 0),
    8: (0x0DCEA8, 1200, 2, 1),
    9: (0x14E00C, 1200, 2, 2),
}


def region_for(res_index: int, quality_index: int) -> int:
    """解像度コードと画質コードから領域番号(1〜9)を返す。"""
    return res_index * 3 + quality_index + 1


# ---------------------------------------------------------------------------
# 送信履歴(TX Picture History)のレイアウト
# HEAD、THUM、DATAの各領域は、4バイトの識別文字列、4バイトLEの領域サイズ、
# ペイロードから成る。領域サイズには識別文字列とサイズフィールド自身の8バイトも含まれる。
# ---------------------------------------------------------------------------

TXH_SOURCE_SIZE_OFFSET = 0x40   # 元となった送信用.datファイルのサイズ(LE32)
TXH_SOURCE_NAME_OFFSET = 0x44   # 元となった送信用.datファイル名(NUL終端)
TXH_HEAD_OFFSET = 0x70          # HEAD領域の先頭
TXH_HEAD_LENGTH = 60
TXH_CALLSIGN_OWN_OFFSET = 0x78  # 自局呼出符号(8バイト)
TXH_CALLSIGN_TO_OFFSET = 0x80   # 宛先呼出符号(8バイト)
TXH_NUMBER_OFFSET = 0x88        # 通し番号とみられる値(送信局が採番か)
TXH_DATETIME_OFFSET = 0x89      # BCDの年月日時分秒(7バイト)
TXH_RESOLUTION_OFFSET = 0x90
TXH_QUALITY_OFFSET = 0x91
TXH_THUM_OFFSET = 0xAC          # THUM領域の先頭。ペイロードは +8
TXH_THUM_LENGTH = 8 + THUM_PAYLOAD_SIZE
TXH_DATA_OFFSET = 0x6B4         # DATA領域の先頭
TXH_DATA_LENGTH = 8 + RECORD_SIZE * 1_200
TXH_DATA_RECORDS_OFFSET = 0x6BC # DATA領域のレコード列先頭

# ---------------------------------------------------------------------------
# 受信履歴(RX Picture History)のレイアウト
# ---------------------------------------------------------------------------

RXH_HEAD_OFFSET = 0x4C          # HEAD領域の先頭
RXH_HEAD_LENGTH = 208
RXH_CALLSIGN_FROM_OFFSET = 0x54  # 送信局呼出符号(8バイト)
RXH_CALLSIGN_TO_OFFSET = 0x5C    # 宛先呼出符号(8バイト)
RXH_NUMBER_OFFSET = 0x64         # 通し番号とみられる値(送信局が採番か)
RXH_DATETIME_OFFSET = 0x65       # BCDの年月日時分秒(7バイト)
RXH_RESOLUTION_OFFSET = 0x6C
RXH_QUALITY_OFFSET = 0x6D
RXH_BITMAP_OFFSET = 0x6E         # 受信ビットマップ(150バイト、MSBが先頭MCU)
RXH_BITMAP_SIZE = 150
RXH_DATA_OFFSET = 0x11C          # DATA領域の先頭
RXH_DATA_LENGTH = 8 + RECORD_SIZE * 1_200
RXH_DATA_RECORDS_OFFSET = 0x124  # DATA領域のレコード列先頭
RXH_RECORD_COUNT = 1200
