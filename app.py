# qr_barcode_generator.py
# -*- coding: utf-8 -*-
"""
批量二维码 / 条形码 生成器（Windows 桌面）
Author: ChatGPT (为用户定制)
依赖: PySide6, pillow, qrcode, python-barcode
安装: pip install PySide6 pillow qrcode python-barcode
运行: python qr_barcode_generator.py
"""

import sys
import os
import io
import math
import re
import threading
from functools import partial

from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageQt
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H

import barcode
from barcode.writer import ImageWriter

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QColor, QIntValidator
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit, QFileDialog,
    QTabWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QComboBox, QSpinBox, QColorDialog, QCheckBox, QMessageBox, QGroupBox,
    QFormLayout, QLineEdit, QProgressBar
)

# -----------------------------
# 辅助函数：颜色 / 图片转换
# -----------------------------
def hex_to_rgba(hex_color: str, alpha=255):
    """将 '#RRGGBB' -> (R,G,B,A)"""
    if not hex_color:
        return (0, 0, 0, alpha)
    s = hex_color.strip()
    if s.startswith('#'):
        s = s[1:]
    if len(s) == 3:
        s = ''.join([c*2 for c in s])
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b, alpha)

def pil_image_to_qpixmap(img: Image.Image):
    """PIL Image -> QPixmap"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    qim = ImageQt.ImageQt(img)
    pix = QPixmap.fromImage(qim)
    return pix

# -----------------------------
# QR 生成核心逻辑
# -----------------------------
def generate_qr_pil(data: str,
                    version: int = None,
                    error_correction: str = "M",
                    out_px: int = 300,
                    padding_px: int = 10,
                    module_color: str = "#000000",
                    back_color: str = "#FFFFFF",
                    outer_eye_color: str = None,
                    inner_eye_color: str = None) -> Image.Image:
    """
    生成二维码 PIL Image
    - version: 1..40 (None 表示自动)
    - error_correction: 'L','M','Q','H'
    - out_px: 目标图像像素边长（正方形） e.g. 300
    - padding_px: 内边距（像素）
    - module_color/back_color: hex str
    - outer_eye_color / inner_eye_color: hex str（可选）
    """
    # 错误修正映射
    ec_map = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
    ec = ec_map.get(error_correction.upper(), ERROR_CORRECT_M)

    # 如果指定版本则不自动 fit，否则自动选择最小版本
    qr = qrcode.QRCode(
        version=version if version else None,
        error_correction=ec,
        box_size=1,
        border=0
    )
    qr.add_data(data)
    try:
        qr.make(fit=(version is None))
    except Exception as e:
        # 如果版本不兼容，尝试自动模式
        qr = qrcode.QRCode(error_correction=ec, box_size=1, border=0)
        qr.add_data(data)
        qr.make(fit=True)

    matrix = qr.get_matrix()  # boolean matrix: True => 黑模块
    modules = len(matrix)  # e.g. 21, 25, ...
    # 计算每个模块的像素大小（尽量接近用户希望的 out_px）
    available_px = max(1, out_px - 2 * padding_px)
    box_size = max(1, available_px // modules)
    qr_px = modules * box_size
    # 生成基础图（不含 padding）
    img = Image.new("RGBA", (qr_px, qr_px), hex_to_rgba(back_color))
    draw = ImageDraw.Draw(img)
    mod_color_rgba = hex_to_rgba(module_color)
    for r in range(modules):
        for c in range(modules):
            if matrix[r][c]:
                x0 = c * box_size
                y0 = r * box_size
                draw.rectangle([x0, y0, x0 + box_size - 1, y0 + box_size - 1], fill=mod_color_rgba)

    # 现在给 finder (眼) 着色（outer 7x7 / inner 3x3），基于模块坐标
    # 找到三角 finder 模块左上角坐标（模块单位）
    finder_coords = [(0, 0), (modules - 7, 0), (0, modules - 7)]
    # 画 outer 7x7、白环 5x5、inner 3x3
    for fx, fy in finder_coords:
        # outer 7x7
        if outer_eye_color:
            col = hex_to_rgba(outer_eye_color)
            x0 = fx * box_size
            y0 = fy * box_size
            draw.rectangle([x0, y0, x0 + 7 * box_size - 1, y0 + 7 * box_size - 1], fill=col)
        # white 5x5 (to make ring)
        bc = hex_to_rgba(back_color)
        x1 = (fx + 1) * box_size
        y1 = (fy + 1) * box_size
        draw.rectangle([x1, y1, x1 + 5 * box_size - 1, y1 + 5 * box_size - 1], fill=bc)
        # inner 3x3
        if inner_eye_color:
            col2 = hex_to_rgba(inner_eye_color)
            x2 = (fx + 2) * box_size
            y2 = (fy + 2) * box_size
            draw.rectangle([x2, y2, x2 + 3 * box_size - 1, y2 + 3 * box_size - 1], fill=col2)
        else:
            # restore inner to module_color if no inner specified
            ic = hex_to_rgba(module_color)
            x2 = (fx + 2) * box_size
            y2 = (fy + 2) * box_size
            draw.rectangle([x2, y2, x2 + 3 * box_size - 1, y2 + 3 * box_size - 1], fill=ic)

    # 增加 padding
    final = ImageOps.expand(img, border=padding_px, fill=hex_to_rgba(back_color))

    # 如果 final 大小还小于期望的 out_px，按 NEAREST 放大到 out_px（保持像素化）
    if final.width != out_px or final.height != out_px:
        final = final.resize((out_px, out_px), Image.NEAREST)

    return final

# -----------------------------
# Barcode 生成核心逻辑
# -----------------------------
def generate_barcode_pil(data: str,
                         barcode_type: str = "code128",
                         bar_width_px: int = 2,
                         bar_height_px: int = 100,
                         margin_px: int = 6,
                         bar_color: str = "#000000",
                         bg_transparent: bool = False,
                         bg_color: str = "#FFFFFF",
                         show_text: bool = True,
                         font_path: str = None,
                         text_pos: str = "bottom",
                         text_align: str = "center") -> Image.Image:
    """
    使用 python-barcode + PIL 生成条形码并按像素调整到我们想要的宽度/高度/颜色
    - barcode_type: 'code128','ean13','ean8','code39','itf','upca' ...
    - bar_width_px: 1..20, 表示窄条宽度（像素）
    - bar_height_px: 1..500
    - margin_px: 左右空白（quiet zone）像素
    - bg_transparent: 背景是否透明
    - show_text: 是否绘制文字（human readable）
    - font_path: 字体文件路径，可为 None（使用默认）
    - text_pos: 'top' or 'bottom'
    - text_align: 'left'/'center'/'right' （只影响显示）
    """
    # 获取 barcode class
    try:
        barcode_cls = barcode.get_barcode_class(barcode_type)
    except Exception as e:
        # fallback
        barcode_cls = barcode.get_barcode_class("code128")

    writer_options = {
        "write_text": show_text,
        # module_width/module_height 这里设置为 1 单位，后面用图像缩放调节到所需 px
        "module_width": 1.0,
        "module_height": 50.0,
        "quiet_zone": 6.5,
        "font_size": 10,
        "text_distance": 5.0,
    }
    writer = ImageWriter()
    # 通过内存写入
    buf = io.BytesIO()
    try:
        obj = barcode_cls(data, writer=writer)
        obj.write(buf, options=writer_options)
    except Exception as e:
        # 如果数据与类型不匹配（如 EAN13 长度不对），降级为 code128
        obj = barcode.get_barcode_class("code128")(data, writer=writer)
        buf = io.BytesIO()
        obj.write(buf, options=writer_options)

    buf.seek(0)
    img = Image.open(buf).convert("RGBA")

    # 现在确定当前最窄黑条的像素宽度（扫描第一行）
    # 转为 L 并二值化
    gray = img.convert("L")
    bw = gray.point(lambda p: 255 if p > 128 else 0, mode='1')
    bw_pix = bw.load()
    width, height = bw.size
    # 找到一行上连续黑段的宽度分布，用来猜测 narrow bar width
    row = height // 2
    runs = []
    cur = None
    curw = 0
    for x in range(width):
        v = bw_pix[x, row]
        if v == 0:  # 黑
            if cur == 'b':
                curw += 1
            else:
                if cur in ('w', None):
                    if curw > 0:
                        runs.append((cur, curw))
                    cur = 'b'
                    curw = 1
        else:
            if cur == 'w':
                curw += 1
            else:
                if cur in ('b', None):
                    if curw > 0:
                        runs.append((cur, curw))
                    cur = 'w'
                    curw = 1
    if curw > 0:
        runs.append((cur, curw))
    # 找到最小的黑段宽
    black_runs = [w for typ, w in runs if typ == 'b']
    actual_narrow = min(black_runs) if black_runs else 1
    scale_x = max(1.0, bar_width_px / actual_narrow)

    # 缩放横向以满足 bar_width_px
    new_w = max(1, int(round(img.width * scale_x)))
    # 纵向则直接调整到用户指定的 bar_height_px（保留文字区域先不变，最后整体缩放处理）
    # 为保证比例与文字位置，我们先把整个图像按 x 缩放，再按 y 缩放到目标高度 + 文字空间
    img = img.resize((new_w, int(round(img.height * scale_x))), Image.NEAREST)

    # 现在裁剪或拉伸到指定高度（bar_height_px + 若有文字则保留文本区域）
    # 计算 actual bar 区域高度（图片中黑条区域顶部到底部），以便拉伸黑条部分到指定 bar_height_px
    # 这里简化处理：将整个图像高度缩放到 bar_height_px 或稍大（若包含文字则加上）
    # 如果有文字，则尝试把条形码主体拉到 bar_height_px，并保持文字尺寸不被拉变形
    if show_text:
        # 假设原图底部有文本区域，大约占原图高度的 0.18，尝试保留该部分
        text_area_est = int(max(8, img.height * 0.18))
        bar_area = img.crop((0, 0, img.width, img.height - text_area_est))
        text_area = img.crop((0, img.height - text_area_est, img.width, img.height))
        # 拉伸 bar_area 到目标高度
        bar_area = bar_area.resize((img.width, max(1, bar_height_px)), Image.NEAREST)
        # 调整 text_area 字体（若用户指定 font_path，我们再重绘文本以更好支持样式）
        # 组装回去
        new_h = bar_area.height + text_area.height
        new_img = Image.new("RGBA", (img.width, new_h), (255, 255, 255, 0 if bg_transparent else 255))
        new_img.paste(bar_area, (0, 0))
        new_img.paste(text_area, (0, bar_area.height))
        img = new_img
    else:
        # 没有文字，直接把整张图拉伸到目标高度
        img = img.resize((img.width, max(1, bar_height_px)), Image.NEAREST)

    # 添加左右 margin
    img = ImageOps.expand(img, border=(margin_px, 0, margin_px, 0), fill=(255, 255, 255, 0 if bg_transparent else 255))

    # 替换颜色：将黑色替换为 bar_color，将白/背景替换为 bg_color/透明
    px = img.load()
    w, h = img.size
    bar_rgba = hex_to_rgba(bar_color)
    bg_rgba = (0, 0, 0, 0) if bg_transparent else hex_to_rgba(bg_color)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            # 将接近黑的像素视为黑
            if r < 100 and g < 100 and b < 100:
                px[x, y] = bar_rgba
            else:
                px[x, y] = bg_rgba

    # 如果需要重新绘制文字（不同字体/对齐/样式），这里可以扩展：为简单起见，使用原有文字
    # TODO: 若提供 font_path，则可以用 PIL 重绘下方文字以支持加粗/斜体/对齐

    return img

# -----------------------------
# 后台生成线程（用于批量生成，避免阻塞 UI）
# -----------------------------
class GeneratorThread(QThread):
    image_generated = Signal(int, object, str)  # index, PIL.Image, text
    progress = Signal(int, int)  # processed, total
    finished_all = Signal()

    def __init__(self, items, mode, options):
        super().__init__()
        self.items = items  # list of strings
        self.mode = mode  # 'qr' or 'barcode'
        self.options = options
        self._running = True

    def run(self):
        total = len(self.items)
        for i, text in enumerate(self.items):
            if not self._running:
                break
            try:
                if self.mode == 'qr':
                    img = generate_qr_pil(
                        data=text,
                        version=self.options.get('version', None),
                        error_correction=self.options.get('error_correction', 'M'),
                        out_px=self.options.get('out_px', 300),
                        padding_px=self.options.get('padding_px', 10),
                        module_color=self.options.get('module_color', '#000000'),
                        back_color=self.options.get('back_color', '#FFFFFF'),
                        outer_eye_color=self.options.get('outer_eye_color', None),
                        inner_eye_color=self.options.get('inner_eye_color', None)
                    )
                else:
                    img = generate_barcode_pil(
                        data=text,
                        barcode_type=self.options.get('barcode_type', 'code128'),
                        bar_width_px=self.options.get('bar_width_px', 2),
                        bar_height_px=self.options.get('bar_height_px', 100),
                        margin_px=self.options.get('margin_px', 6),
                        bar_color=self.options.get('bar_color', '#000000'),
                        bg_transparent=self.options.get('bg_transparent', False),
                        bg_color=self.options.get('bg_color', '#FFFFFF'),
                        show_text=self.options.get('show_text', True),
                        font_path=self.options.get('font_path', None),
                        text_pos=self.options.get('text_pos', 'bottom'),
                        text_align=self.options.get('text_align', 'center'),
                    )
            except Exception as e:
                # 如果生成失败，生成一张错误图片
                img = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
                d = ImageDraw.Draw(img)
                d.text((10, 10), "ERROR", fill=(255, 255, 255, 255))
            self.image_generated.emit(i, img, text)
            self.progress.emit(i + 1, total)
        self.finished_all.emit()

    def stop(self):
        self._running = False

# -----------------------------
# 主窗口 UI
# -----------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量二维码 / 条形码 生成器")
        self.resize(1200, 800)
        self.generated_images = []  # 存储 (text, PIL.Image)
        self.thumb_size = 150  # 缩略图显示大小
        self.generator_thread = None

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 顶部：批量输入 + 文件上传
        input_group = QGroupBox("批量输入（支持逗号、分号、换行分隔）")
        input_layout = QHBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("把要编码的内容粘贴到这里，或使用右侧的文件上传按钮。")
        input_layout.addWidget(self.text_input, 3)

        right_col = QVBoxLayout()
        self.load_file_btn = QPushButton("上传文件")
        self.load_file_btn.clicked.connect(self.load_file)
        right_col.addWidget(self.load_file_btn)

        right_col.addSpacing(10)
        right_col.addWidget(QLabel("分隔符（自动/逗号/分号/换行）"))
        self.sep_combo = QComboBox()
        self.sep_combo.addItems(["自动", ",", ";", "换行"])
        right_col.addWidget(self.sep_combo)

        right_col.addStretch()
        input_layout.addLayout(right_col, 1)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group, 1)

        # 中部：Tabs（二维码 / 条形码） + 生成按钮
        self.tabs = QTabWidget()
        self.qr_tab = QWidget()
        self.barcode_tab = QWidget()
        self.tabs.addTab(self.qr_tab, "二维码")
        self.tabs.addTab(self.barcode_tab, "条形码")
        self._build_qr_tab()
        self._build_barcode_tab()
        main_layout.addWidget(self.tabs, 0)

        # 中心显示区：滚动显示区域
        center_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setSpacing(10)
        self.scroll_widget.setLayout(self.grid_layout)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)
        center_layout.addWidget(self.scroll_area)
        main_layout.addLayout(center_layout, 1)

        # 进度条与导出控件
        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar, 4)

        # 导出选项
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["PDF", "PNG", "JPG"])
        bottom_layout.addWidget(QLabel("导出格式："))
        bottom_layout.addWidget(self.export_format_combo)
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        bottom_layout.addWidget(self.export_btn)

        main_layout.addLayout(bottom_layout, 0)

    # -----------------------------
    # QR TAB UI
    # -----------------------------
    def _build_qr_tab(self):
        layout = QHBoxLayout()
        form = QFormLayout()

        # 版本（21*21 ~ 177*177） -> QR version 1..40
        self.qr_version_combo = QComboBox()
        self.qr_version_combo.addItem("自动")
        for v in range(1, 41):
            modules = 21 + 4 * (v - 1)
            self.qr_version_combo.addItem(f"版本 {v} ({modules}×{modules})", v)
        form.addRow("二维码版本：", self.qr_version_combo)

        # 容错率
        self.qr_ec_combo = QComboBox()
        self.qr_ec_combo.addItems(["L", "M", "Q", "H"])
        self.qr_ec_combo.setCurrentText("M")
        form.addRow("容错率：", self.qr_ec_combo)

        # 每个二维码图像大小像素选择（100~1000）
        self.qr_size_spin = QSpinBox()
        self.qr_size_spin.setRange(100, 1000)
        self.qr_size_spin.setValue(300)
        form.addRow("生成图像大小（px）：", self.qr_size_spin)

        # 内边距 0~100px
        self.qr_padding_spin = QSpinBox()
        self.qr_padding_spin.setRange(0, 200)
        self.qr_padding_spin.setValue(10)
        form.addRow("内边距（px）：", self.qr_padding_spin)

        # 颜色选择：码颜色、背景色、外眼色、内眼色
        self.qr_module_color_btn = QPushButton("选择")
        self.qr_module_color_display = QLineEdit("#000000")
        self.qr_module_color_btn.clicked.connect(partial(self._choose_color, self.qr_module_color_display))
        form.addRow("码颜色：", self._hbox(self.qr_module_color_display, self.qr_module_color_btn))

        self.qr_back_color_btn = QPushButton("选择")
        self.qr_back_color_display = QLineEdit("#FFFFFF")
        self.qr_back_color_btn.clicked.connect(partial(self._choose_color, self.qr_back_color_display))
        form.addRow("背景色：", self._hbox(self.qr_back_color_display, self.qr_back_color_btn))

        self.qr_outer_eye_btn = QPushButton("选择")
        self.qr_outer_eye_display = QLineEdit("")  # 可留空
        self.qr_outer_eye_btn.clicked.connect(partial(self._choose_color, self.qr_outer_eye_display))
        form.addRow("码外眼颜色（可空）：", self._hbox(self.qr_outer_eye_display, self.qr_outer_eye_btn))

        self.qr_inner_eye_btn = QPushButton("选择")
        self.qr_inner_eye_display = QLineEdit("")  # 可留空
        self.qr_inner_eye_btn.clicked.connect(partial(self._choose_color, self.qr_inner_eye_display))
        form.addRow("码内眼颜色（可空）：", self._hbox(self.qr_inner_eye_display, self.qr_inner_eye_btn))

        # 生成按钮
        self.qr_generate_btn = QPushButton("生成二维码")
        self.qr_generate_btn.clicked.connect(self.on_generate_qr)
        form.addRow(self.qr_generate_btn)

        layout.addLayout(form)
        self.qr_tab.setLayout(layout)

    # -----------------------------
    # Barcode TAB UI
    # -----------------------------
    def _build_barcode_tab(self):
        layout = QHBoxLayout()
        form = QFormLayout()

        # 条码类型选择
        self.barcode_type_combo = QComboBox()
        # 常见类型（python-barcode 支持的）
        types = ["code128", "ean13", "ean8", "upc", "code39", "itf"]
        self.barcode_type_combo.addItems(types)
        form.addRow("条码类型：", self.barcode_type_combo)

        # 条宽 1~20 px
        self.bar_width_spin = QSpinBox()
        self.bar_width_spin.setRange(1, 20)
        self.bar_width_spin.setValue(2)
        form.addRow("条宽（px）：", self.bar_width_spin)

        # 间距（图片间距）0~100 px
        self.bar_margin_spin = QSpinBox()
        self.bar_margin_spin.setRange(0, 200)
        self.bar_margin_spin.setValue(6)
        form.addRow("左右边距（px）：", self.bar_margin_spin)

        # 条码高度 1~500
        self.bar_height_spin = QSpinBox()
        self.bar_height_spin.setRange(1, 500)
        self.bar_height_spin.setValue(100)
        form.addRow("条码高度（px）：", self.bar_height_spin)

        # 颜色、背景是否透明
        self.bar_color_display = QLineEdit("#000000")
        self.bar_color_btn = QPushButton("选择")
        self.bar_color_btn.clicked.connect(partial(self._choose_color, self.bar_color_display))
        form.addRow("条码颜色：", self._hbox(self.bar_color_display, self.bar_color_btn))

        self.bar_bg_trans_check = QCheckBox("透明背景")
        self.bar_bg_color_display = QLineEdit("#FFFFFF")
        self.bar_bg_color_btn = QPushButton("选择")
        self.bar_bg_color_btn.clicked.connect(partial(self._choose_color, self.bar_bg_color_display))
        form.addRow(self.bar_bg_trans_check, self._hbox(self.bar_bg_color_display, self.bar_bg_color_btn))

        # 是否显示文字、字体选择、文字位置、对齐、样式（简化：只支持字体文件选择）
        self.bar_show_text_chk = QCheckBox("显示文字")
        self.bar_show_text_chk.setChecked(True)
        form.addRow("显示文字：", self.bar_show_text_chk)

        self.bar_font_line = QLineEdit("")
        self.bar_font_btn = QPushButton("选择字体文件")
        self.bar_font_btn.clicked.connect(self.choose_font_file)
        form.addRow("文字字体（可选）：", self._hbox(self.bar_font_line, self.bar_font_btn))

        self.bar_text_pos_combo = QComboBox()
        self.bar_text_pos_combo.addItems(["下方", "上方"])
        form.addRow("文字位置：", self.bar_text_pos_combo)

        self.bar_text_align_combo = QComboBox()
        self.bar_text_align_combo.addItems(["左", "中", "右"])
        form.addRow("对齐方式：", self.bar_text_align_combo)

        # 文字样式（边距、大小、加粗、斜体）
        self.bar_text_margin_spin = QSpinBox()
        self.bar_text_margin_spin.setRange(0, 100)
        self.bar_text_margin_spin.setValue(5)
        form.addRow("文字边距（px）：", self.bar_text_margin_spin)

        self.bar_text_size_spin = QSpinBox()
        self.bar_text_size_spin.setRange(6, 72)
        self.bar_text_size_spin.setValue(12)
        form.addRow("文字大小：", self.bar_text_size_spin)

        self.bar_text_bold_chk = QCheckBox("加粗")
        self.bar_text_italic_chk = QCheckBox("斜体")
        form.addRow(self._hbox(self.bar_text_bold_chk, self.bar_text_italic_chk))

        # 生成按钮
        self.bar_generate_btn = QPushButton("生成条形码")
        self.bar_generate_btn.clicked.connect(self.on_generate_barcode)
        form.addRow(self.bar_generate_btn)

        layout.addLayout(form)
        self.barcode_tab.setLayout(layout)

    # -----------------------------
    # UI 交互辅助
    # -----------------------------
    def _hbox(self, *widgets):
        w = QWidget()
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            lay.addWidget(widget)
        w.setLayout(lay)
        return w

    def _choose_color(self, target_lineedit: QLineEdit):
        initial = QColor(target_lineedit.text()) if target_lineedit.text() else QColor(0, 0, 0)
        col = QColorDialog.getColor(initial, self, "选择颜色")
        if col.isValid():
            hexv = col.name()
            target_lineedit.setText(hexv)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt *.csv);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = f.read()
            self.text_input.setPlainText(data)
            QMessageBox.information(self, "文件加载", f"已加载 {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "文件错误", f"读取失败: {e}")

    def choose_font_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字体文件（.ttf/.otf）", "", "字体文件 (*.ttf *.otf);;所有文件 (*)")
        if path:
            self.bar_font_line.setText(path)

    def _parse_input(self) -> list:
        raw = self.text_input.toPlainText().strip()
        if not raw:
            return []
        sep = self.sep_combo.currentText()
        if sep == "自动":
            parts = re.split(r'[,\n;\r]+', raw)
        elif sep == ",":
            parts = [p.strip() for p in raw.split(",")]
        elif sep == ";":
            parts = [p.strip() for p in raw.split(";")]
        elif sep == "换行":
            parts = [p.strip() for p in re.split(r'[\r\n]+', raw)]
        else:
            parts = re.split(r'[,\n;\r]+', raw)
        # 过滤空项
        parts = [p for p in parts if p]
        return parts

    # -----------------------------
    # 生成事件：二维码 / 条码
    # -----------------------------
    def on_generate_qr(self):
        items = self._parse_input()
        if not items:
            QMessageBox.warning(self, "无数据", "请先在上方输入或上传要生成的数据。")
            return
        # 读取参数
        v_index = self.qr_version_combo.currentIndex()
        version = None
        if v_index != 0:
            version = self.qr_version_combo.currentData()
        options = {
            'version': version,
            'error_correction': self.qr_ec_combo.currentText(),
            'out_px': self.qr_size_spin.value(),
            'padding_px': self.qr_padding_spin.value(),
            'module_color': self.qr_module_color_display.text() or "#000000",
            'back_color': self.qr_back_color_display.text() or "#FFFFFF",
            'outer_eye_color': self.qr_outer_eye_display.text() or None,
            'inner_eye_color': self.qr_inner_eye_display.text() or None
        }
        # 清空现有显示
        self.clear_display()
        self.start_generation(items, mode='qr', options=options)

    def on_generate_barcode(self):
        items = self._parse_input()
        if not items:
            QMessageBox.warning(self, "无数据", "请先在上方输入或上传要生成的数据。")
            return
        options = {
            'barcode_type': self.barcode_type_combo.currentText(),
            'bar_width_px': self.bar_width_spin.value(),
            'bar_height_px': self.bar_height_spin.value(),
            'margin_px': self.bar_margin_spin.value(),
            'bar_color': self.bar_color_display.text() or "#000000",
            'bg_transparent': self.bar_bg_trans_check.isChecked(),
            'bg_color': self.bar_bg_color_display.text() or "#FFFFFF",
            'show_text': self.bar_show_text_chk.isChecked(),
            'font_path': self.bar_font_line.text() or None,
            'text_pos': 'top' if self.bar_text_pos_combo.currentText() == '上方' else 'bottom',
            'text_align': {'左': 'left', '中': 'center', '右': 'right'}[self.bar_text_align_combo.currentText()],
            'text_margin': self.bar_text_margin_spin.value(),
            'text_size': self.bar_text_size_spin.value(),
            'text_bold': self.bar_text_bold_chk.isChecked(),
            'text_italic': self.bar_text_italic_chk.isChecked()
        }
        self.clear_display()
        self.start_generation(items, mode='barcode', options=options)

    def clear_display(self):
        # 清理 grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.generated_images = []

    def start_generation(self, items, mode, options):
        # 启动线程
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(items))
        self.progress_bar.setValue(0)

        self.generator_thread = GeneratorThread(items, mode, options)
        self.generator_thread.image_generated.connect(self.on_image_generated)
        self.generator_thread.progress.connect(self.on_progress)
        self.generator_thread.finished_all.connect(self.on_generation_finished)
        self.generator_thread.start()

    def on_image_generated(self, idx, pil_img, text):
        # 存储图像（完整尺寸）
        self.generated_images.append((text, pil_img))
        # 生成缩略图以显示
        thumb = pil_img.copy()
        thumb.thumbnail((self.thumb_size, self.thumb_size), Image.LANCZOS)
        pix = pil_image_to_qpixmap(thumb)
        label = QLabel()
        label.setPixmap(pix)
        label.setFixedSize(self.thumb_size + 10, self.thumb_size + 30)
        label.setScaledContents(False)
        label.setToolTip(text)
        # 点击缩略图弹出大图
        label.mousePressEvent = partial(self._on_thumb_clicked, pil_img, text)
        pos = self.grid_layout.count()
        cols = max(1, self.scroll_widget.width() // (self.thumb_size + 20))
        row = pos // 6
        col = pos % 6
        self.grid_layout.addWidget(label, row, col)

    def _on_thumb_clicked(self, pil_img, text, ev):
        # 弹窗显示大图，并提供保存单张按钮
        w = QWidget()
        w.setWindowTitle(text[:50])
        v = QVBoxLayout(w)
        pix = pil_image_to_qpixmap(pil_img)
        lbl = QLabel()
        lbl.setPixmap(pix)
        lbl.setScaledContents(True)
        lbl.setMinimumSize(300, 300)
        v.addWidget(lbl)
        btn = QPushButton("保存此图")
        def save_one():
            fmt = QFileDialog.getSaveFileName(self, "保存图片", f"{text}.png", "PNG 文件 (*.png);;JPG 文件 (*.jpg)")
            if fmt and fmt[0]:
                fp = fmt[0]
                try:
                    pil_img.save(fp)
                    QMessageBox.information(self, "保存", f"已保存到 {fp}")
                except Exception as e:
                    QMessageBox.critical(self, "保存失败", str(e))
        btn.clicked.connect(save_one)
        v.addWidget(btn)
        w.resize(600, 600)
        w.show()

    def on_progress(self, p, total):
        self.progress_bar.setValue(p)
        QApplication.processEvents()

    def on_generation_finished(self):
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", "全部生成完毕。")

    # -----------------------------
    # 导出
    # -----------------------------
    def export_results(self):
        if not self.generated_images:
            QMessageBox.warning(self, "没有数据", "当前没有已生成的图片，请先生成。")
            return
        fmt = self.export_format_combo.currentText()
        if fmt == "PDF":
            path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", "batch_codes.pdf", "PDF 文件 (*.pdf)")
            if not path:
                return
            # PIL 可以把多张图合成 pdf（所有图需为 RGB）
            imgs = []
            for _, im in self.generated_images:
                if im.mode in ("RGBA", "P"):
                    imgs.append(im.convert("RGB"))
                else:
                    imgs.append(im.copy())
            try:
                imgs[0].save(path, "PDF", resolution=100.0, save_all=True, append_images=imgs[1:])
                QMessageBox.information(self, "导出成功", f"已导出到 {path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))
        else:
            # PNG / JPG：选择文件夹并批量保存
            folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
            if not folder:
                return
            ext = "png" if fmt == "PNG" else "jpg"
            try:
                for i, (text, im) in enumerate(self.generated_images, 1):
                    safe = re.sub(r'[\\/:*?"<>|]', '_', text)[:60] or f"code_{i:04d}"
                    fname = os.path.join(folder, f"{safe}.{ext}")
                    if ext == 'jpg':
                        rgb = im.convert("RGB")
                        rgb.save(fname, quality=95)
                    else:
                        im.save(fname)
                QMessageBox.information(self, "导出成功", f"已导出到 {folder}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

# -----------------------------
# 启动程序
# -----------------------------
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
