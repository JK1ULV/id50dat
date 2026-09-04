# id50dat — ID-50 Image `.dat` Codec

English | [日本語](https://github.com/JK1ULV/id50dat/blob/main/README.ja.md)

id50dat is a Python library with CLI and GUI tools for reading and writing image `.dat` files stored by the ICOM ID-50 on a microSD card.
The file format implementation is based on findings documented in the Japanese book *ID-50で遊ぶ D-STAR画像伝送* (23 Lab, 2026).

## Supported formats

| Format | Identifier | Encode | Decode |
|---|---|:---:|:---:|
| Transmit `.dat` file | `TX Picture Data` | Yes | Yes |
| TX history `.dat` file (`TxHistNNN.dat`) | `TX Picture History` | No | Yes |
| RX history `.dat` file (`RxHistNNN.dat`) | `RX Picture History` | No | Yes |

Encoding creates nine regions covering three resolutions and three quality levels, plus a `THUM` thumbnail, from a single image.

## Features

- Encode images as transmit `.dat` files
  - Accepts any image format supported by Pillow
  - Fits images to the required aspect ratio by padding, cropping, or stretching
- Decode transmit, TX history, and RX history `.dat` files
  - Reconstructs JPEG files from the entropy-coded data in each record without recompressing the received image data
  - Supports PNG output through both the CLI and GUI
  - Fills missing RX regions with black by default; a different color or transparency can be selected
  - Generates output filenames from header information and other metadata in the `.dat` file

## Requirements and installation

Python 3.10 or later is required. Pillow 12.3.0 is installed automatically. The GUI also requires tkinter.

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

The display language is selected automatically from the operating system. Use the
global `--lang` option before the command to override it:

```console
id50dat --lang en info 20260820_120000.dat
id50dat --lang ja gui
```

`--lang auto` restores automatic selection. The `ID50DAT_LANG` environment
variable can also be set to `ja` or `en`; `--lang` takes precedence.

```console
# Show the file type and metadata
id50dat info 20260820_120000.dat

# Decode a transmit .dat file into nine JPEG files and one THUM PNG
id50dat decode 20260820_120000.dat -o out/

# Decode a history file into JPEG; TX history also produces a THUM PNG
id50dat decode RxHist000.dat -o out/

# Decode all .dat files in the current directory (including in PowerShell)
id50dat decode *.dat -o out/

# Output PNG
id50dat decode RxHist000.dat -o out/ -f png

# Fill missing regions in RX history with a color
id50dat decode RxHist000.dat -o out/ --missing navy

# Make missing regions transparent and output PNG
id50dat decode RxHist000.dat -o out/ -f png --missing transparent

# Decode one region only (--region 9 = 640x480, high quality)
id50dat decode 20260820_120000.dat -o out/ --region 9

# Encode an image as a transmit .dat file
id50dat encode photo.png -o 20260820_120000.dat --fit pad

# Launch the GUI
id50dat gui
```

`--fit` controls how a non-4:3 image is fitted: `pad` adds black borders and is the default, `crop` center-crops the image, and `stretch` ignores the original aspect ratio.

The `encode` output filename must end in `.dat`. The name part (excluding the extension) must be at most 23 bytes in Shift_JIS due to an ID-50 hardware limitation.

Use `-f` or `--format` to select `jpg` (default) or `png`.

The CLI reports an error if an output file already exists (`--overwrite` to replace). The GUI shows a confirmation dialog.

`--missing` sets the fill color for unreceived parts in RX history. The default is `black`; color names and RGB values (`ff8800`, `#ff8800`) are accepted. `transparent` is available only with PNG output.

The `info`, `decode`, and `encode` commands also accept the short forms `-i`, `-d`, and `-e`.

## Output filenames

The CLI generates output filenames using the following rules. The GUI suggests the same names in its save dialogs. Text enclosed in `{...}` is a placeholder.

| Type | Pattern | Example |
|---|---|---|
| Transmit `.dat` | `{input}_{width}x{height}_{quality}.{format}` | 640x480 high-quality JPEG from `20260820_120000.dat`: `20260820_120000_640x480_high.jpg` |
| TX history | `{datetime}_{source}_{own}_to_{destination}_{width}x{height}_{quality}.{format}` | `20260820_123456_photo_JA1ABC_to_CQCQCQ_640x480_high.jpg` |
| RX history | `{datetime}_{from}_to_{destination}_{width}x{height}_{quality}.{format}` | `20260820_120000_JA1ABC_to_CQCQCQ_640x480_high.png` |

`{datetime}` is the timestamp stored in the `.dat` file. TX history names include it to distinguish repeated transmissions of the same source file and their THUM images. THUM images follow the same pattern without the `{width}x{height}_{quality}` part.

If a TX history source filename is empty or unusable, it is omitted. If the timestamp is unusable, the input filename is used instead. Characters not allowed in Windows filenames are replaced.

## Using the library

```python
from pathlib import Path

from PIL import Image

import id50dat

# Decode
obj = id50dat.load("20260820_120000.dat")           # Detect the file type
if obj.kind == "tx_dat":
    jpeg_bytes = obj.region_jpeg(9)                 # 640x480, high quality
    obj.thum_image().save("thum.png")
elif obj.kind == "rx_history":
    print(obj.describe())                           # Callsigns, timestamp, missing count
    Path("received.jpg").write_bytes(obj.to_jpeg())
    obj.to_image(missing="transparent").save("received.png")

# Encode
with Image.open("photo.png") as image:
    dat = id50dat.TxPictureData.from_image(image, fit="pad")
dat.save("20260820_120000.dat")
```

Main APIs:

- `id50dat.detect(path)` — detect the type (`"tx_dat"`, `"tx_history"`, `"rx_history"`, and others)
- `id50dat.load(path)` — return `TxPictureData`, `TxHistory`, or `RxHistory` according to the detected type
- `TxPictureData.from_image(image, fit)`, `.to_bytes()`, and `.save(path)` — encode
- `TxPictureData.region_jpeg(n)`, `.region_image(n)`, and `.thum_image()` — decode
- `TxHistory` — `.to_jpeg()`, `.to_image()`, `.describe()`, and `.thum_image()`
- `RxHistory` — `.to_jpeg(missing=...)`, `.to_image(missing=...)`, and `.describe()`
- `id50dat.tx_data_image_name()` and `id50dat.history_image_name()` — generate output filenames
- `id50dat.dat_filename_fits(path)`, `.dat_filename_problem(path)`, `.dat_filename_message(path)` — check whether a `.dat` filename is usable on the ID-50
- `id50dat.set_language("ja" | "en" | "auto")` — set the language used by messages and `describe()`

## License

MIT License
