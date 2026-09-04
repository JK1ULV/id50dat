# id50dat — ID-50画像`.dat`コーデック

[English](https://github.com/JK1ULV/id50dat/blob/main/README.md) | 日本語

ICOM ID-50がmicroSDカードへ保存する画像用`.dat`ファイルを読み書きするPythonライブラリ、およびCLI／GUIツールです。
ファイル形式は、同人誌「ID-50で遊ぶD-STAR画像伝送」（23らぼ、2026年）での解析結果に基づいています。

## 対応形式

| 形式 | 識別文字列 | エンコード | デコード |
|---|---|:---:|:---:|
| 送信用`.dat`ファイル | `TX Picture Data` | ○ | ○ |
| 送信履歴`.dat`ファイル (`TxHistNNN.dat`) | `TX Picture History` | — | ○ |
| 受信履歴`.dat`ファイル (`RxHistNNN.dat`) | `RX Picture History` | — | ○ |

- エンコードでは、1枚の画像から3解像度×3画質（計9種類）の画像データ（`DAT1`〜`DAT9`）と`THUM`を生成します。

## 機能

- 送信用`.dat`ファイルにエンコード
  - Pillowが読み込める画像形式に対応
  - アスペクト比に合わせた黒帯挿入、トリミング、引き伸ばし
- 送信用および送信・受信履歴の`.dat`ファイルをデコード
  - エントロピー符号化データを再圧縮せずにJPEGとして再構成
  - CLIとGUIでPNGも選択可能
  - 受信できなかった部分の色補完（透明も可）
  - ヘッダー情報等からの出力ファイル名自動生成

## 必要環境

Python 3.10以降が必要です。Pillow 12.3.0はインストール時に自動的にインストールされます。GUIを使用する場合はtkinterも必要です。

```console
git clone https://github.com/JK1ULV/id50dat.git
cd id50dat
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install .
```

macOS:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install .
```

## CLI

表示言語はOSの言語設定から自動判定します。明示的に切り替える場合は、`info`や`decode`などのサブコマンドより前に`--lang`を指定します。

```console
id50dat --lang ja info 20260820_120000.dat
id50dat --lang en gui
```

`--lang auto`で自動判定に戻ります。環境変数`ID50DAT_LANG`へ`ja`または`en`を設定することもできます。`--lang`を指定した場合は、環境変数より優先されます。

```console
# 種別と内容の表示
id50dat info 20260820_120000.dat

# デコード(送信用`.dat`ファイル -> 各解像度・画質のJPEG 9枚とTHUMのPNG)
id50dat decode 20260820_120000.dat -o out/

# デコード(履歴 -> JPEG。送信履歴はTHUMのPNGも出力)
id50dat decode RxHist000.dat -o out/

# カレントディレクトリの`.dat`ファイルを一括デコード(PowerShellでも使用可能)
id50dat decode *.dat -o out/

# PNGで出力
id50dat decode RxHist000.dat -o out/ -f png

# 未受信部分を色で塗りつぶす
id50dat decode RxHist000.dat -o out/ --missing navy

# 未受信部分を透明にしてPNGで出力
id50dat decode RxHist000.dat -o out/ -f png --missing transparent

# 特定領域だけ(--region 9 = 640×480・高画質)
id50dat decode 20260820_120000.dat -o out/ --region 9

# エンコード(画像 -> 送信用`.dat`ファイル)
id50dat encode photo.png -o 20260820_120000.dat --fit pad

# GUI
id50dat gui
```

`--fit`は元画像が4:3でない場合の合わせ方で、`pad`（余白を黒で埋める。既定）、`crop`（中央で切り取る）、`stretch`（引き伸ばす）から指定します。

`encode`の出力ファイル名は拡張子を`.dat`とし、ファイル名（拡張子を除く）はID-50本体の仕様によりShift_JISで23バイト以内（半角23文字、または全角11文字と半角1文字）にする必要があります。

`-f`／`--format`でデコード画像の形式を`jpg`（既定）または`png`から選びます。

CLIでは出力先ファイルが既に存在する場合、エラーになります（`--overwrite`で上書き）。GUIでは保存時に上書き確認ダイアログが表示されます。

`--missing`は、受信履歴で受信できなかった部分の塗りつぶし色を指定します。省略時は`black`で、色名やRGB値（`ff8800`、`#ff8800`）も使えます。`transparent`はPNG出力時のみ指定できます。

`info`、`decode`、`encode`は`-i`、`-d`、`-e`でも指定できます。

## 出力ファイル名

CLIは次の規則で出力ファイル名を自動生成します。GUIでは同じ名前を保存ダイアログの初期値として提案します。`{...}`はプレースホルダです。

| 種別 | 一般形 | 具体例 |
|---|---|---|
| 送信用`.dat` | `{入力名}_{幅}x{高さ}_{画質}.{形式}` | 入力`20260820_120000.dat`の640×480・高画質JPEG: `20260820_120000_640x480_high.jpg` |
| 送信履歴 | `{日時}_{元送信用ファイル名}_{自局}_to_{宛先}_{幅}x{高さ}_{画質}.{形式}` | `20260820_123456_photo_JA1ABC_to_CQCQCQ_640x480_high.jpg` |
| 受信履歴 | `{日時}_{送信元}_to_{宛先}_{幅}x{高さ}_{画質}.{形式}` | `20260820_120000_JA1ABC_to_CQCQCQ_640x480_high.png` |

`{日時}`は`.dat`が保持する履歴の日時です。同じ送信用ファイルを繰り返し送信した履歴とTHUMを区別するため、送信履歴にも日時を含めています。THUMは同じ規則から`{幅}x{高さ}_{画質}`を除いた名前になります。

送信履歴の元ファイル名が取得できない場合は省略されます。日時が無効な場合は入力ファイル名で代替します。Windowsで禁止されている文字は自動的に置換されます。

## ライブラリとして使う

```python
from pathlib import Path

from PIL import Image

import id50dat

# デコード
obj = id50dat.load("20260820_120000.dat")           # 種別を自動判定
if obj.kind == "tx_dat":
    jpeg_bytes = obj.region_jpeg(9)                 # 640×480・高画質
    obj.thum_image().save("thum.png")
elif obj.kind == "rx_history":
    print(obj.describe())                           # 呼出符号、日時、欠損数など
    Path("received.jpg").write_bytes(obj.to_jpeg())
    obj.to_image(missing="transparent").save("received.png")

# エンコード
with Image.open("photo.png") as image:
    dat = id50dat.TxPictureData.from_image(image, fit="pad")
dat.save("20260820_120000.dat")
```

主なAPI:

- `id50dat.detect(path)` — 種別判定(`"tx_dat"` / `"tx_history"` / `"rx_history"`など)
- `id50dat.load(path)` — 種別に応じて`TxPictureData` / `TxHistory` / `RxHistory`を返す
- `TxPictureData.from_image(image, fit)` / `.to_bytes()` / `.save(path)` — エンコード
- `TxPictureData.region_jpeg(n)` / `.region_image(n)` / `.thum_image()` — デコード
- `TxHistory` — `.to_jpeg()`、`.to_image()`、`.describe()`、`.thum_image()`
- `RxHistory` — `.to_jpeg(missing=...)`、`.to_image(missing=...)`、`.describe()`
- `id50dat.tx_data_image_name()` / `id50dat.history_image_name()` — 出力ファイル名の生成
- `id50dat.dat_filename_fits(path)` / `.dat_filename_problem(path)` / `.dat_filename_message(path)` — `.dat`ファイル名がID-50で使えるかの検査
- `id50dat.set_language("ja" | "en" | "auto")` — メッセージおよび`describe()`の表示言語を設定

## ライセンス

MIT License
