"""id50datのtkinter GUI。"""

from __future__ import annotations

import io
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import RxHistory, TxHistory, TxPictureData, load
from .constants import (
    QUALITY_NAMES,
    REGIONS,
    RESOLUTIONS,
    region_for,
)
from .i18n import tr, trf
from .jpegio import RecordTooLargeError
from .naming import (
    dat_filename_message,
    dat_filename_problem,
    history_image_name,
    history_thumbnail_name,
    tx_data_image_name,
    tx_data_thumbnail_name,
)

PREVIEW_SIZE = (480, 360)

DAT_FILETYPES = [(tr("ID-50 .datファイル"), "*.dat"), (tr("すべてのファイル"), "*.*")]
IMAGE_FILETYPES = [
    (tr("画像ファイル"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
    (tr("すべてのファイル"), "*.*"),
]
EXPORT_FILETYPES = {
    "jpg": [("JPEG", "*.jpg")],
    "png": [("PNG", "*.png")],
}


def _preview_photo(image: Image.Image) -> ImageTk.PhotoImage:
    img = image.convert("RGB").copy()
    img.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)


def _confirm_batch_overwrite(paths: list[Path]) -> bool:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return True
    shown = "\n".join(str(path) for path in existing[:3])
    if len(existing) > 3:
        shown += "\n" + trf("ほか {count} 件のファイル", count=len(existing) - 3)
    return messagebox.askyesno(
        "id50dat",
        trf(
            "既存の{count}ファイルを上書きしますか？\n\n{files}",
            count=len(existing),
            files=shown,
        ),
    )


class DecodeTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.obj = None
        self.path: Path | None = None
        self._photo = None  # 参照保持

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text=tr(".datファイルを開く"), command=self.open_file).pack(
            side="left"
        )
        self.info_var = tk.StringVar(value=tr("ファイルを開いてください。"))
        ttk.Label(self, textvariable=self.info_var, justify="left").pack(
            fill="x", pady=(8, 4)
        )

        sel = ttk.Frame(self)
        sel.pack(fill="x")
        ttk.Label(sel, text=tr("解像度:")).pack(side="left")
        self.res_var = tk.StringVar(value="640×480")
        self.res_box = ttk.Combobox(
            sel, textvariable=self.res_var, state="disabled", width=9,
            values=[f"{w}×{h}" for w, h in RESOLUTIONS.values()],
        )
        self.res_box.pack(side="left", padx=(2, 10))
        ttk.Label(sel, text=tr("画質:")).pack(side="left")
        self.qual_var = tk.StringVar(value=tr(QUALITY_NAMES[2]))
        self.qual_box = ttk.Combobox(
            sel, textvariable=self.qual_var, state="disabled", width=8,
            values=[tr(name) for name in QUALITY_NAMES.values()],
        )
        self.qual_box.pack(side="left", padx=2)
        self.res_box.bind("<<ComboboxSelected>>", lambda _e: self.update_preview())
        self.qual_box.bind("<<ComboboxSelected>>", lambda _e: self.update_preview())

        self.canvas = ttk.Label(self, relief="sunken", anchor="center")
        self.canvas.pack(fill="both", expand=True, pady=8)

        btns = ttk.Frame(self)
        btns.pack(fill="x")
        self.save_btn = ttk.Menubutton(
            btns, text=tr("画像を保存"), state="disabled"
        )
        self.save_btn.pack(side="left")
        self.save_menu = tk.Menu(self.save_btn, tearoff=False)
        self.save_btn.configure(menu=self.save_menu)

        self.save_all_btn = ttk.Menubutton(
            btns, text=tr("全9領域を一括保存"), state="disabled"
        )
        self.save_all_btn.pack(side="left", padx=4)
        self.save_all_menu = tk.Menu(self.save_all_btn, tearoff=False)
        self.save_all_menu.add_command(
            label=tr("JPEGとして保存"), command=lambda: self.save_all("jpg")
        )
        self.save_all_menu.add_command(
            label=tr("PNGとして保存"), command=lambda: self.save_all("png")
        )
        self.save_all_btn.configure(menu=self.save_all_menu)

        self.save_thum_btn = ttk.Button(
            btns,
            text=tr("THUMをPNGで保存"),
            command=self.save_thum,
            state="disabled",
        )
        self.save_thum_btn.pack(side="left")

        self._configure_save_menu()

    # ------------------------------------------------------------------

    def open_file(self):
        name = filedialog.askopenfilename(filetypes=DAT_FILETYPES)
        if not name:
            return
        try:
            self.obj = load(name)
        except (OSError, ValueError) as e:
            messagebox.showerror("id50dat", str(e))
            return
        self.path = Path(name)
        is_dat = isinstance(self.obj, TxPictureData)
        state = "readonly" if is_dat else "disabled"
        self.res_box.configure(state=state)
        self.qual_box.configure(state=state)
        self.save_btn.configure(state="normal")
        self.save_all_btn.configure(state="normal" if is_dat else "disabled")
        has_thum = is_dat or isinstance(self.obj, TxHistory)
        self.save_thum_btn.configure(state="normal" if has_thum else "disabled")
        self._configure_save_menu()
        if is_dat:
            self.info_var.set(trf(
                "{name}: 送信用.datファイル (DAT1〜DAT9とTHUM)",
                name=self.path.name,
            ))
        else:
            self.info_var.set(f"{self.path.name}\n{self.obj.describe()}")
        self.update_preview()

    def _current_jpeg(self, missing="black") -> bytes:
        if isinstance(self.obj, TxPictureData):
            res = self.res_box["values"].index(self.res_var.get())
            qual = [tr(name) for name in QUALITY_NAMES.values()].index(
                self.qual_var.get()
            )
            return self.obj.region_jpeg(region_for(res, qual))
        if isinstance(self.obj, RxHistory):
            return self.obj.to_jpeg(missing)
        return self.obj.to_jpeg()

    def _current_image(self, missing="black") -> Image.Image:
        if isinstance(self.obj, TxPictureData):
            res = self.res_box["values"].index(self.res_var.get())
            qual = [tr(name) for name in QUALITY_NAMES.values()].index(
                self.qual_var.get()
            )
            return self.obj.region_image(region_for(res, qual))
        if isinstance(self.obj, RxHistory):
            return self.obj.to_image(missing)
        return self.obj.to_image()

    def update_preview(self):
        if self.obj is None:
            return
        try:
            jpeg = self._current_jpeg()
            with Image.open(io.BytesIO(jpeg)) as img:
                self._photo = _preview_photo(img)
        except Exception as e:  # 破損データでもGUIは落とさない
            messagebox.showerror(
                "id50dat", trf("プレビューに失敗しました: {error}", error=e)
            )
            return
        self.canvas.configure(image=self._photo)

    # ------------------------------------------------------------------

    def _configure_save_menu(self):
        self.save_menu.delete(0, "end")
        if isinstance(self.obj, RxHistory) and self.obj.missing_count:
            self._add_missing_save_menus()
            return
        self.save_menu.add_command(
            label=tr("JPEGとして保存"), command=lambda: self.save_image("jpg")
        )
        self.save_menu.add_command(
            label=tr("PNGとして保存"), command=lambda: self.save_image("png")
        )

    def _add_missing_save_menus(self):
        self.save_jpeg_menu = tk.Menu(self.save_menu, tearoff=False)
        self.save_jpeg_menu.add_command(
            label=tr("黒で塗りつぶす"), command=lambda: self.save_image("jpg")
        )
        self.save_jpeg_menu.add_command(
            label=tr("色を選択..."), command=lambda: self.save_with_color("jpg")
        )
        self.save_menu.add_cascade(
            label=tr("JPEGとして保存"), menu=self.save_jpeg_menu
        )

        self.save_png_menu = tk.Menu(self.save_menu, tearoff=False)
        self.save_png_menu.add_command(
            label=tr("黒で塗りつぶす"), command=lambda: self.save_image("png")
        )
        self.save_png_menu.add_command(
            label=tr("色を選択..."), command=lambda: self.save_with_color("png")
        )
        self.save_png_menu.add_command(
            label=tr("透明にする"),
            command=lambda: self.save_image("png", "transparent"),
        )
        self.save_menu.add_cascade(label=tr("PNGとして保存"), menu=self.save_png_menu)

    def save_with_color(self, image_format: str):
        _rgb, color = colorchooser.askcolor(title=tr("未受信部分の色"))
        if color:
            self.save_image(image_format, color)

    def save_image(self, image_format: str, missing="black"):
        if self.obj is None:
            return
        input_stem = self.path.stem if self.path else "image"
        if isinstance(self.obj, TxPictureData):
            res = self.res_box["values"].index(self.res_var.get())
            qual = [tr(name) for name in QUALITY_NAMES.values()].index(
                self.qual_var.get()
            )
            name = tx_data_image_name(input_stem, region_for(res, qual), image_format)
        else:
            name = history_image_name(self.obj, input_stem, image_format)
        name = filedialog.asksaveasfilename(
            defaultextension=f".{image_format}",
            filetypes=EXPORT_FILETYPES[image_format],
            initialfile=name,
        )
        if name:
            path = Path(name)
            try:
                if image_format == "jpg":
                    path.write_bytes(self._current_jpeg(missing))
                else:
                    self._current_image(missing).save(path, format="PNG")
            except (OSError, ValueError) as e:
                messagebox.showerror(
                    "id50dat", trf("画像を保存できません: {error}", error=e)
                )

    def save_all(self, image_format: str):
        folder = filedialog.askdirectory()
        if not folder:
            return
        outdir = Path(folder)
        input_stem = self.path.stem if self.path else "image"
        output_paths = [
            outdir / tx_data_image_name(input_stem, n, image_format)
            for n in REGIONS
        ]
        output_paths.append(outdir / tx_data_thumbnail_name(input_stem))
        if not _confirm_batch_overwrite(output_paths):
            return
        try:
            for n in REGIONS:
                name = tx_data_image_name(input_stem, n, image_format)
                output_path = outdir / name
                if image_format == "jpg":
                    output_path.write_bytes(self.obj.region_jpeg(n))
                else:
                    self.obj.region_image(n).save(output_path, format="PNG")
            self.obj.thum_image().save(outdir / tx_data_thumbnail_name(input_stem))
        except (OSError, ValueError) as e:
            messagebox.showerror(
                "id50dat", trf("画像を保存できません: {error}", error=e)
            )
            return
        messagebox.showinfo(
            "id50dat", trf("{path} に10個のファイルを保存しました。", path=outdir)
        )

    def save_thum(self):
        input_stem = self.path.stem if self.path else "image"
        if isinstance(self.obj, TxHistory):
            initialfile = history_thumbnail_name(self.obj, input_stem)
        else:
            initialfile = tx_data_thumbnail_name(input_stem)
        name = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile=initialfile,
        )
        if name:
            try:
                self.obj.thum_image().save(name)
            except (OSError, ValueError) as e:
                messagebox.showerror(
                    "id50dat", trf("THUMを保存できません: {error}", error=e)
                )


class EncodeTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.image: Image.Image | None = None
        self._photo = None

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text=tr("画像を開く"), command=self.open_image).pack(
            side="left"
        )
        ttk.Label(top, text=tr("アスペクト比4:3への調整:")).pack(
            side="left", padx=(12, 2)
        )
        self.fit_var = tk.StringVar(value="pad")
        for value, label in (
            ("pad", tr("余白")),
            ("crop", tr("切り取り")),
            ("stretch", tr("引き伸ばし")),
        ):
            ttk.Radiobutton(
                top, text=label, value=value, variable=self.fit_var
            ).pack(side="left")

        self.info_var = tk.StringVar(
            value=tr("画像を開いてください。")
        )
        ttk.Label(self, textvariable=self.info_var, justify="left").pack(
            fill="x", pady=(8, 4)
        )
        self.canvas = ttk.Label(self, relief="sunken", anchor="center")
        self.canvas.pack(fill="both", expand=True, pady=8)

        self.save_btn = ttk.Button(
            self,
            text=tr("送信用.datファイルとして保存"),
            command=self.save_dat,
            state="disabled",
        )
        self.save_btn.pack(anchor="w")

    def open_image(self):
        name = filedialog.askopenfilename(filetypes=IMAGE_FILETYPES)
        if not name:
            return
        try:
            with Image.open(name) as img:
                self.image = img.convert("RGB")
        except Exception as e:
            messagebox.showerror(
                "id50dat", trf("画像を開けません: {error}", error=e)
            )
            return
        self.info_var.set(
            f"{Path(name).name}  ({self.image.width}×{self.image.height})"
        )
        self._photo = _preview_photo(self.image)
        self.canvas.configure(image=self._photo)
        self.save_btn.configure(state="normal")

    def save_dat(self):
        if self.image is None:
            return
        name = filedialog.asksaveasfilename(
            defaultextension=".dat",
            filetypes=DAT_FILETYPES,
            initialfile=datetime.now().strftime("%Y%m%d_%H%M%S") + ".dat",
        )
        if not name:
            return
        problem = dat_filename_problem(name)
        if problem is not None:
            messagebox.showerror("id50dat", dat_filename_message(name, problem))
            return
        try:
            dat = TxPictureData.from_image(self.image, fit=self.fit_var.get())
        except RecordTooLargeError as e:
            messagebox.showerror(
                "id50dat",
                tr("この画像は1 MCUあたりの符号サイズがレコード上限を超えるため変換できません。")
                + f"\n{e}",
            )
            return
        try:
            dat.save(name)
        except (OSError, ValueError) as e:
            messagebox.showerror(
                "id50dat",
                trf("送信用.datファイルを保存できません: {error}", error=e),
            )
            return
        messagebox.showinfo("id50dat", trf("{path} を作成しました。", path=name))


def run():
    root = tk.Tk()
    root.title(tr("id50dat — ID-50画像.datツール"))
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    notebook.add(DecodeTab(notebook), text=tr("デコード"))
    notebook.add(EncodeTab(notebook), text=tr("エンコード"))
    root.minsize(560, 520)
    root.mainloop()


if __name__ == "__main__":
    run()
