# -*- coding: utf-8 -*-
"""
批量二维码 / 条形码 生成器（Windows 桌面）
Author: ChatGPT (为用户定制), modified by Grok
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
import gc
from functools import partial
import logging
import time

from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageQt
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
import barcode
from barcode.writer import ImageWriter

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit, QFileDialog,
    QTabWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QComboBox, QSpinBox, QColorDialog, QCheckBox, QMessageBox, QGroupBox,
    QFormLayout, QLineEdit, QProgressBar, QDialog
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 页面尺寸定义（像素，基于300 DPI）
PAGE_SIZES = {
    "A3": (3508, 4961),  # 297mm x 420mm
    "A4": (2480, 3508),  # 210mm x 297mm
    "A5": (1748, 2480),  # 148mm x 210mm
}

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
                    left_right_padding_px: int = 10,
                    top_bottom_padding_px: int = 10,
                    module_color: str = "#000000",
                    back_color: str = "#FFFFFF",
                    outer_eye_color: str = None,
                    inner_eye_color: str = None,
                    show_text: bool = False,
                    font_path: str = None,
                    text_pos: str = "bottom",
                    text_align: str = "center",
                    text_margin: int = 5,
                    text_size: int = 12,
                    text_bold: bool = False,
                    text_italic: bool = False) -> Image.Image:
    """
    生成二维码 PIL Image，支持文字大小和样式（加粗/斜体），非正方形画布
    """
    ec_map = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
    ec = ec_map.get(error_correction.upper(), ERROR_CORRECT_M)

    qr = qrcode.QRCode(
        version=version if version else None,
        error_correction=ec,
        box_size=1,
        border=0
    )
    qr.add_data(data)
    try:
        qr.make(fit=(version is None))
    except Exception:
        qr = qrcode.QRCode(error_correction=ec, box_size=1, border=0)
        qr.add_data(data)
        qr.make(fit=True)

    matrix = qr.get_matrix()
    modules = len(matrix)
    available_px = max(1, out_px - 2 * left_right_padding_px)
    box_size = max(1, available_px // modules)
    qr_px = modules * box_size
    img = Image.new("RGBA", (qr_px, qr_px), hex_to_rgba(back_color))
    draw = ImageDraw.Draw(img)
    mod_color_rgba = hex_to_rgba(module_color)
    for r in range(modules):
        for c in range(modules):
            if matrix[r][c]:
                x0 = c * box_size
                y0 = r * box_size
                draw.rectangle([x0, y0, x0 + box_size - 1, y0 + box_size - 1], fill=mod_color_rgba)

    finder_coords = [(0, 0), (modules - 7, 0), (0, modules - 7)]
    for fx, fy in finder_coords:
        if outer_eye_color:
            col = hex_to_rgba(outer_eye_color)
            x0 = fx * box_size
            y0 = fy * box_size
            draw.rectangle([x0, y0, x0 + 7 * box_size - 1, y0 + 7 * box_size - 1], fill=col)
        bc = hex_to_rgba(back_color)
        x1 = (fx + 1) * box_size
        y1 = (fy + 1) * box_size
        draw.rectangle([x1, y1, x1 + 5 * box_size - 1, y1 + 5 * box_size - 1], fill=bc)
        if inner_eye_color:
            col2 = hex_to_rgba(inner_eye_color)
            x2 = (fx + 2) * box_size
            y2 = (fy + 2) * box_size
            draw.rectangle([x2, y2, x2 + 3 * box_size - 1, y2 + 3 * box_size - 1], fill=col2)
        else:
            ic = hex_to_rgba(module_color)
            x2 = (fx + 2) * box_size
            y2 = (fy + 2) * box_size
            draw.rectangle([x2, y2, x2 + 3 * box_size - 1, y2 + 3 * box_size - 1], fill=ic)

    # 添加文字
    if show_text:
        # 选择字体：优先用户指定字体，支持加粗/斜体
        font = None
        font_name = font_path if font_path and os.path.exists(font_path) else None
        if font_name:
            if text_bold and text_italic:
                try_font = font_name.replace(".ttf", "bi.ttf").replace(".otf", "bi.otf")
            elif text_bold:
                try_font = font_name.replace(".ttf", "bd.ttf").replace(".otf", "bd.otf")
            elif text_italic:
                try_font = font_name.replace(".ttf", "i.ttf").replace(".otf", "i.otf")
            else:
                try_font = font_name
            try:
                font = ImageFont.truetype(try_font, size=max(6, text_size))
                logger.info(f"Loaded font: {try_font}, size: {text_size}")
            except Exception as e:
                logger.warning(f"Failed to load font {try_font}: {e}")
                font_name = None

        if not font:
            try:
                if text_bold and text_italic:
                    font = ImageFont.truetype("arialbi.ttf", size=max(6, text_size))
                elif text_bold:
                    font = ImageFont.truetype("arialbd.ttf", size=max(6, text_size))
                elif text_italic:
                    font = ImageFont.truetype("ariali.ttf", size=max(6, text_size))
                else:
                    font = ImageFont.truetype("arial.ttf", size=max(6, text_size))
                logger.info(f"Loaded fallback font: Arial, size: {text_size}")
            except Exception as e:
                logger.warning(f"Failed to load Arial font: {e}")
                font = ImageFont.load_default()
                text_size = min(text_size, 12)
                logger.info(f"Using Pillow default font, size limited to: {text_size}")

        # 计算文字尺寸
        text_bbox = draw.textbbox((0, 0), data, font=font)
        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        extra_height = text_h + text_margin * 2

        # 创建新画布以容纳文字
        new_h = qr_px + extra_height
        new_img = Image.new("RGBA", (qr_px, new_h), hex_to_rgba(back_color))
        draw = ImageDraw.Draw(new_img)

        # 放置二维码和文字
        if text_pos == "bottom":
            new_img.paste(img, (0, 0))
            text_y = qr_px + text_margin
        else:
            new_img.paste(img, (0, extra_height))
            text_y = text_margin

        # 计算文字对齐
        if text_align == "center":
            text_x = (qr_px - text_w) // 2
        elif text_align == "right":
            text_x = qr_px - text_w - text_margin
        else:
            text_x = text_margin

        # 渲染文字
        draw.text((text_x, text_y), data, font=font, fill=mod_color_rgba)
        img = new_img

    # 添加左右和上下内边距
    final = ImageOps.expand(img, border=(left_right_padding_px, top_bottom_padding_px, left_right_padding_px, top_bottom_padding_px), fill=hex_to_rgba(back_color))
    final_h = (qr_px + extra_height if show_text else qr_px) + 2 * top_bottom_padding_px

    # 调整到目标宽度（保持比例，纵向可能非正方形）
    if final.width != out_px:
        scale = out_px / final.width
        final = final.resize((out_px, int(final.height * scale)), Image.NEAREST)

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
                        text_align: str = "center",
                        text_margin: int = 5,
                        text_size: int = 12,
                        text_bold: bool = False,
                        text_italic: bool = False) -> Image.Image:
    try:
        barcode_cls = barcode.get_barcode_class(barcode_type)
    except Exception:
        barcode_cls = barcode.get_barcode_class("code128")

    writer_options = {
        "write_text": show_text,
        "module_width": 1.0,
        "module_height": 50.0,
        "quiet_zone": 6.5,
        "font_size": text_size,
        "text_distance": text_margin,
    }
    writer = ImageWriter()
    buf = io.BytesIO()
    try:
        obj = barcode_cls(data, writer=writer)
        obj.write(buf, options=writer_options)
    except Exception:
        obj = barcode.get_barcode_class("code128")(data, writer=writer)
        buf = io.BytesIO()
        obj.write(buf, options=writer_options)

    buf.seek(0)
    img = Image.open(buf).convert("RGBA")

    gray = img.convert("L")
    bw = gray.point(lambda p: 255 if p > 128 else 0, mode='1')
    bw_pix = bw.load()
    width, height = bw.size
    row = height // 2
    runs = []
    cur = None
    curw = 0
    for x in range(width):
        v = bw_pix[x, row]
        if v == 0:
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
    black_runs = [w for typ, w in runs if typ == 'b']
    actual_narrow = min(black_runs) if black_runs else 1
    scale_x = max(1.0, bar_width_px / actual_narrow)

    new_w = max(1, int(round(img.width * scale_x)))
    img = img.resize((new_w, int(round(img.height * scale_x))), Image.NEAREST)

    if show_text:
        text_area_est = int(max(8, img.height * 0.18))
        bar_area = img.crop((0, 0, img.width, img.height - text_area_est))
        text_area = img.crop((0, img.height - text_area_est, img.width, img.height))
        bar_area = bar_area.resize((img.width, max(1, bar_height_px)), Image.NEAREST)
        new_h = bar_area.height + text_area.height + text_margin * 2
        new_img = Image.new("RGBA", (img.width, new_h), (255, 255, 255, 0 if bg_transparent else 255))
        if text_pos == "bottom":
            new_img.paste(bar_area, (0, 0))
            new_img.paste(text_area, (0, bar_area.height + text_margin))
        else:
            new_img.paste(bar_area, (0, text_area.height + text_margin))
            new_img.paste(text_area, (0, 0))
        img = new_img
    else:
        img = img.resize((img.width, max(1, bar_height_px)), Image.NEAREST)

    img = ImageOps.expand(img, border=(margin_px, margin_px, margin_px, margin_px), fill=(255, 255, 255, 0 if bg_transparent else 255))

    px = img.load()
    w, h = img.size
    bar_rgba = hex_to_rgba(bar_color)
    bg_rgba = (0, 0, 0, 0) if bg_transparent else hex_to_rgba(bg_color)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 100 and g < 100 and b < 100:
                px[x, y] = bar_rgba
            else:
                px[x, y] = bg_rgba

    return img

# -----------------------------
# 后台生成线程
# -----------------------------
class GeneratorThread(QThread):
    image_generated = Signal(int, object, str)
    progress = Signal(int, int)
    finished_all = Signal()
    error = Signal(str)

    def __init__(self, items, mode, options, batch_size=1000, max_display=50):
        super().__init__()
        self.items = items[:max_display]  # 限制生成前50个
        self.mode = mode
        self.options = options
        self.batch_size = batch_size
        self.max_display = max_display
        self._running = True

    def run(self):
        total = len(self.items)
        try:
            for batch_start in range(0, total, self.batch_size):
                if not self._running:
                    break
                batch = self.items[batch_start:batch_start + self.batch_size]
                for i, text in enumerate(batch):
                    global_idx = batch_start + i
                    if not self._running:
                        break
                    try:
                        if self.mode == 'qr':
                            img = generate_qr_pil(
                                data=text,
                                version=self.options.get('version', None),
                                error_correction=self.options.get('error_correction', 'M'),
                                out_px=self.options.get('out_px', 300),
                                left_right_padding_px=self.options.get('left_right_padding_px', 10),
                                top_bottom_padding_px=self.options.get('top_bottom_padding_px', 10),
                                module_color=self.options.get('module_color', '#000000'),
                                back_color=self.options.get('back_color', '#FFFFFF'),
                                outer_eye_color=self.options.get('outer_eye_color', None),
                                inner_eye_color=self.options.get('inner_eye_color', None),
                                show_text=self.options.get('show_text', False),
                                font_path=self.options.get('font_path', None),
                                text_pos=self.options.get('text_pos', 'bottom'),
                                text_align=self.options.get('text_align', 'center'),
                                text_margin=self.options.get('text_margin', 5),
                                text_size=self.options.get('text_size', 12),
                                text_bold=self.options.get('text_bold', False),
                                text_italic=self.options.get('text_italic', False)
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
                                text_margin=self.options.get('text_margin', 5),
                                text_size=self.options.get('text_size', 12),
                                text_bold=self.options.get('text_bold', False),
                                text_italic=self.options.get('text_italic', False)
                            )
                        if global_idx < self.max_display:
                            self.image_generated.emit(global_idx, img, text)
                    except Exception as e:
                        img = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
                        d = ImageDraw.Draw(img)
                        d.text((10, 10), "ERROR", fill=(255, 255, 255, 255))
                        if global_idx < self.max_display:
                            self.image_generated.emit(global_idx, img, text)
                    self.progress.emit(global_idx + 1, total)
                    img = None
                    gc.collect()
                gc.collect()
        except MemoryError:
            self.error.emit("内存不足，请减少每次生成的数据量或降低图像分辨率。")
            return
        except Exception as e:
            self.error.emit(f"生成失败：{str(e)}")
            return
        self.finished_all.emit()

    def stop(self):
        self._running = False

# -----------------------------
# 导出进度对话框
# -----------------------------
class ProgressDialog(QDialog):
    def __init__(self, total_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出进度")
        self.setModal(True)
        self.setFixedSize(400, 150)
        self.total_items = total_items
        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(total_items)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备开始导出...")
        layout.addWidget(self.status_label)

        self.cancel_btn = QPushButton("取消导出")
        layout.addWidget(self.cancel_btn)

        self.setLayout(layout)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, status):
        self.status_label.setText(status)

# -----------------------------
# 导出线程
# -----------------------------
class ExportThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, items, mode, options, fmt, arrangement, cols_per_row, output_path, page_size, auto_size, parent=None):
        super().__init__(parent)
        self.items = items
        self.mode = mode
        self.options = options
        self.fmt = fmt
        self.arrangement = arrangement
        self.cols_per_row = cols_per_row
        self.output_path = output_path
        self.page_size = page_size
        self.auto_size = auto_size
        self._running = True
        self.temp_files = []

    def run(self):
        try:
            if self.fmt == "PDF":
                self._export_pdf()
            else:
                self._export_images()
        except MemoryError:
            self.error.emit("内存不足，请减少图像分辨率或数据量。")
        except Exception as e:
            self.error.emit(f"导出失败：{str(e)}")
        finally:
            self._cleanup_temp_files()

    def _export_pdf(self):
        a4_width, a4_height = PAGE_SIZES[self.page_size]
        margin = self.options.get('left_right_padding_px', 0)
        spacing = self.options.get('top_bottom_padding_px', 0)
        codes_per_row = self.cols_per_row if self.arrangement == "横向排列" else 1
        codes_per_col = 3 if self.arrangement == "竖向排列" else 1
        codes_per_page = codes_per_row * codes_per_col
        pages_per_pdf = 100  # 每100页生成一个PDF

        # 计算图像大小
        max_width = 0
        max_height = 0
        sample_size = min(10, len(self.items))
        if self.auto_size and self.arrangement == "横向排列":
            available_width = (a4_width - 2 * margin - (codes_per_row - 1) * spacing) // codes_per_row
            self.options['out_px'] = max(100, available_width)
            if self.mode == 'barcode':
                self.options['bar_width_px'] = max(1, available_width // 50)  # 假设条宽比例

        for text in self.items[:sample_size]:
            if not self._running:
                return
            img = generate_qr_pil(text, **self.options) if self.mode == 'qr' else generate_barcode_pil(text, **self.options)
            max_width = max(max_width, img.width)
            max_height = max(max_height, img.height)
            img.close()
            img = None
            gc.collect()

        current_page = None
        draw = None
        x, y = margin, margin
        page_count = 0
        item_count = 0
        segment_images = []
        pdf_index = 1

        for i, text in enumerate(self.items):
            if not self._running:
                break

            if current_page is None:
                current_page = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
                draw = ImageDraw.Draw(current_page)
                self.status.emit(f"正在导出第 {page_count + 1} 页，第 {item_count + 1} 条数据")

            img = generate_qr_pil(text, **self.options) if self.mode == 'qr' else generate_barcode_pil(text, **self.options)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img = img.resize((max_width, max_height), Image.LANCZOS)

            if self.arrangement == "横向排列":
                if x + max_width > a4_width - margin:
                    x = margin
                    y += max_height + spacing
                if y + max_height > a4_height - margin:
                    if current_page is not None:
                        temp_path = f"{self.output_path}.temp_{page_count}.png"
                        current_page.save(temp_path, "PNG", optimize=True)
                        self.temp_files.append(temp_path)
                        segment_images.append(current_page)
                        current_page.close()
                        current_page = None
                        draw = None
                        page_count += 1
                        x, y = margin, margin
                        if len(segment_images) >= pages_per_pdf:
                            self._save_segment_pdf(segment_images, pdf_index)
                            segment_images = []
                            pdf_index += 1
                        if not self._running:
                            break
                        current_page = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
                        draw = ImageDraw.Draw(current_page)
                        self.status.emit(f"正在导出第 {page_count + 1} 页，第 {item_count + 1} 条数据")
                if self._running and current_page is not None:
                    current_page.paste(img, (x, y))
                    draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                    x += max_width + spacing
            else:
                if y + max_height > a4_height - margin:
                    if current_page is not None:
                        temp_path = f"{self.output_path}.temp_{page_count}.png"
                        current_page.save(temp_path, "PNG", optimize=True)
                        self.temp_files.append(temp_path)
                        segment_images.append(current_page)
                        current_page.close()
                        current_page = None
                        draw = None
                        page_count += 1
                        x, y = margin, margin
                        if len(segment_images) >= pages_per_pdf:
                            self._save_segment_pdf(segment_images, pdf_index)
                            segment_images = []
                            pdf_index += 1
                        if not self._running:
                            break
                        current_page = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
                        draw = ImageDraw.Draw(current_page)
                        self.status.emit(f"正在导出第 {page_count + 1} 页，第 {item_count + 1} 条数据")
                if self._running and current_page is not None:
                    current_page.paste(img, (x, y))
                    draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                    y += max_height + spacing

            item_count += 1
            self.progress.emit(item_count)
            img.close()
            img = None
            gc.collect()
            if item_count % 100 == 0:
                QApplication.processEvents()

        # 保存最后一页
        if self._running and current_page is not None:
            temp_path = f"{self.output_path}.temp_{page_count}.png"
            current_page.save(temp_path, "PNG", optimize=True)
            self.temp_files.append(temp_path)
            segment_images.append(current_page)
            current_page.close()
            current_page = None
            draw = None
            page_count += 1

        # 保存剩余的页面到最后一个PDF
        if self._running and segment_images:
            self._save_segment_pdf(segment_images, pdf_index)

        if self._running:
            self.finished.emit(f"已导出 {len(self.items)} 个二维码/条形码到 {self.output_path}")

    def _save_segment_pdf(self, images, pdf_index):
        if not images or not self._running:
            return
        output_path = f"{self.output_path.rsplit('.', 1)[0]}_{pdf_index}.pdf"
        self.status.emit(f"正在生成PDF文件 {output_path}")
        start_time = time.time()
        try:
            images[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=images[1:])
            logger.info(f"Created PDF {output_path}, {len(images)} pages, time: {time.time() - start_time:.2f}s")
        except Exception as e:
            logger.error(f"Failed to create PDF {output_path}: {str(e)}")
            self.error.emit(f"生成PDF失败：{str(e)}")
            return

    def _export_images(self):
        a4_width, a4_height = PAGE_SIZES[self.page_size]
        margin = self.options.get('left_right_padding_px', 0)
        spacing = self.options.get('top_bottom_padding_px', 0)
        codes_per_row = self.cols_per_row if self.arrangement == "横向排列" else 1
        codes_per_col = 3 if self.arrangement == "竖向排列" else 1
        codes_per_page = codes_per_row * codes_per_col

        if self.auto_size and self.arrangement == "横向排列":
            available_width = (a4_width - 2 * margin - (codes_per_row - 1) * spacing) // codes_per_row
            self.options['out_px'] = max(100, available_width)
            if self.mode == 'barcode':
                self.options['bar_width_px'] = max(1, available_width // 50)

        if len(self.items) > codes_per_page:
            reply = QMessageBox.question(
                None, "数据量警告",
                f"当前 {len(self.items)} 条数据超过单页容量（{codes_per_page} 个）。选择“是”保存为单独文件，选择“否”仅导出单页。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                folder = QFileDialog.getExistingDirectory(None, "选择输出文件夹")
                if not folder:
                    self.finished.emit("")
                    return
                ext = "png" if self.fmt == "PNG" else "jpg"
                for i, text in enumerate(self.items):
                    if not self._running:
                        return
                    img = generate_qr_pil(text, **self.options) if self.mode == 'qr' else generate_barcode_pil(text, **self.options)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    safe_text = "".join(c for c in text if c.isalnum() or c in "-_")[:50]
                    fname = os.path.join(folder, f"code_{i+1}_{safe_text}.{ext}")
                    if ext == 'jpg':
                        img.save(fname, quality=95)
                    else:
                        img.save(fname)
                    self.progress.emit(i + 1)
                    self.status.emit(f"正在导出第 {i + 1} 条数据")
                    img.close()
                    img = None
                    gc.collect()
                    if (i + 1) % 100 == 0:
                        QApplication.processEvents()
                self.finished.emit(f"已将 {len(self.items)} 个二维码/条形码导出到 {folder}")
                return

        folder = QFileDialog.getExistingDirectory(None, "选择输出文件夹")
        if not folder:
            self.finished.emit("")
            return
        ext = "png" if self.fmt == "PNG" else "jpg"
        output_img = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
        draw = ImageDraw.Draw(output_img)
        x, y = margin, margin
        max_width = 0
        max_height = 0

        for i, text in enumerate(self.items[:codes_per_page]):
            if not self._running:
                return
            img = generate_qr_pil(text, **self.options) if self.mode == 'qr' else generate_barcode_pil(text, **self.options)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            max_width = max(max_width, img.width)
            max_height = max(max_height, img.height)
            img = img.resize((max_width, max_height), Image.LANCZOS)
            if self.arrangement == "横向排列":
                if x + max_width > a4_width - margin:
                    x = margin
                    y += max_height + spacing
                if y + max_height > a4_height - margin:
                    break
                output_img.paste(img, (x, y))
                draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                x += max_width + spacing
            else:
                if y + max_height > a4_height - margin:
                    break
                output_img.paste(img, (x, y))
                draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                y += max_height + spacing
            self.progress.emit(i + 1)
            self.status.emit(f"正在导出第 {i + 1} 条数据")
            img.close()
            img = None
            gc.collect()
            if (i + 1) % 100 == 0:
                QApplication.processEvents()
        fname = os.path.join(folder, f"batch_codes.{ext}")
        if ext == 'jpg':
            output_img.save(fname, quality=95)
        else:
            output_img.save(fname)
        output_img.close()
        output_img = None
        gc.collect()
        self.finished.emit(f"已导出 {min(codes_per_page, len(self.items))} 个二维码/条形码到 {fname}")

    def _cleanup_temp_files(self):
        for temp_file in self.temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
        self.temp_files = []

    def stop(self):
        self._running = False

# -----------------------------
# 主窗口 UI
# -----------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量二维码 / 条形码 生成器")
        self.resize(1200, 900)
        self.generated_images = []
        self.preview_image = None
        self.max_display_items = 50
        self.batch_size = 1000
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._on_param_changed)

        self._build_ui()
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #333;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005ba1;
            }
            QPushButton:pressed {
                background-color: #003c71;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                background-color: #fff;
            }
            QComboBox {
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QScrollArea {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            QCheckBox, QComboBox, QSpinBox, QLineEdit {
                margin: 2px;
            }
            QLabel {
                color: #333;
            }
        """)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # 左侧：输入区域和参数设置
        left_layout = QVBoxLayout()

        input_group = QGroupBox("批量输入（支持逗号、分号、换行分隔）")
        input_layout = QHBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("输入要编码的内容，或使用右侧文件上传按钮")
        input_layout.addWidget(self.text_input, 3)

        right_col = QVBoxLayout()
        self.load_file_btn = QPushButton("上传文件")
        self.load_file_btn.clicked.connect(self.load_file)
        right_col.addWidget(self.load_file_btn)
        right_col.addSpacing(10)
        right_col.addWidget(QLabel("分隔符："))
        self.sep_combo = QComboBox()
        self.sep_combo.addItems(["自动", ",", ";", "换行"])
        right_col.addWidget(self.sep_combo)
        right_col.addStretch()
        input_layout.addLayout(right_col, 1)
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group, 2)

        self.tabs = QTabWidget()
        self.qr_tab = QWidget()
        self.barcode_tab = QWidget()
        self.tabs.addTab(self.qr_tab, "二维码")
        self.tabs.addTab(self.barcode_tab, "条形码")
        self._build_qr_tab()
        self._build_barcode_tab()
        left_layout.addWidget(self.tabs, 1)

        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar, 3)

        bottom_layout.addWidget(QLabel("页面尺寸："))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A3", "A4", "A5"])
        self.page_size_combo.setCurrentText("A4")
        bottom_layout.addWidget(self.page_size_combo)

        bottom_layout.addWidget(QLabel("排列方式："))
        self.arrangement_combo = QComboBox()
        self.arrangement_combo.addItems(["横向排列", "竖向排列"])
        self.arrangement_combo.currentTextChanged.connect(self._update_ui_for_arrangement)
        bottom_layout.addWidget(self.arrangement_combo)

        bottom_layout.addWidget(QLabel("每行个数（横向排列）："))
        self.cols_per_row_combo = QComboBox()
        self.cols_per_row_combo.addItems([str(i) for i in range(1, 11)])
        self.cols_per_row_combo.setCurrentText("7")
        bottom_layout.addWidget(self.cols_per_row_combo)

        bottom_layout.addWidget(QLabel("导出格式："))
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["PDF", "PNG", "JPG"])
        bottom_layout.addWidget(self.export_format_combo)
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        bottom_layout.addWidget(self.export_btn)
        left_layout.addLayout(bottom_layout, 0)

        main_layout.addLayout(left_layout, 2)

        # 右侧：预览区域
        right_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_widget.setLayout(QVBoxLayout())
        self.scroll_widget.layout().addWidget(self.preview_label)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)
        right_layout.addWidget(self.scroll_area)
        main_layout.addLayout(right_layout, 3)

        self.setLayout(main_layout)

    def _update_ui_for_arrangement(self):
        is_horizontal = self.arrangement_combo.currentText() == "横向排列"
        self.cols_per_row_combo.setVisible(is_horizontal)
        self.qr_size_label.setVisible(not is_horizontal or not self.qr_auto_size_chk.isChecked())
        self.qr_size_spin.setVisible(not is_horizontal or not self.qr_auto_size_chk.isChecked())
        self.qr_auto_size_chk.setVisible(is_horizontal)
        self.bar_width_label.setVisible(not is_horizontal or not self.bar_auto_size_chk.isChecked())
        self.bar_width_spin.setVisible(not is_horizontal or not self.bar_auto_size_chk.isChecked())
        self.bar_auto_size_chk.setVisible(is_horizontal)

    def _connect_param_signals(self):
        pass  # 移除自动更新预览的信号连接

    def _debounce_update_preview(self):
        pass  # 移除防抖更新逻辑

    def _on_param_changed(self):
        pass  # 移除参数变化时的自动更新

    def _build_qr_tab(self):
        layout = QHBoxLayout()
        form = QGridLayout()
        form.setSpacing(10)

        self.qr_version_combo = QComboBox()
        self.qr_version_combo.addItem("自动")
        for v in range(1, 41):
            modules = 21 + 4 * (v - 1)
            self.qr_version_combo.addItem(f"版本 {v} ({modules}×{modules})", v)
        form.addWidget(QLabel("二维码版本："), 0, 0)
        form.addWidget(self.qr_version_combo, 0, 1)

        self.qr_ec_combo = QComboBox()
        self.qr_ec_combo.addItems(["L", "M", "Q", "H"])
        self.qr_ec_combo.setCurrentText("M")
        form.addWidget(QLabel("容错率："), 1, 0)
        form.addWidget(self.qr_ec_combo, 1, 1)

        self.qr_size_label = QLabel("图像大小（px）：")
        self.qr_size_spin = QSpinBox()
        self.qr_size_spin.setRange(100, 1000)
        self.qr_size_spin.setValue(300)
        self.qr_auto_size_chk = QCheckBox("自动尺寸")
        self.qr_auto_size_chk.stateChanged.connect(self._update_ui_for_arrangement)
        form.addWidget(self.qr_size_label, 2, 0)
        form.addWidget(self._hbox(self.qr_size_spin, self.qr_auto_size_chk), 2, 1)

        self.qr_left_right_padding_spin = QSpinBox()
        self.qr_left_right_padding_spin.setRange(0, 200)
        self.qr_left_right_padding_spin.setValue(10)
        form.addWidget(QLabel("左右内边距（px）："), 3, 0)
        form.addWidget(self.qr_left_right_padding_spin, 3, 1)

        self.qr_top_bottom_padding_spin = QSpinBox()
        self.qr_top_bottom_padding_spin.setRange(0, 200)
        self.qr_top_bottom_padding_spin.setValue(10)
        form.addWidget(QLabel("上下内边距（px）："), 4, 0)
        form.addWidget(self.qr_top_bottom_padding_spin, 4, 1)

        self.qr_text_margin_spin = QSpinBox()
        self.qr_text_margin_spin.setRange(0, 100)
        self.qr_text_margin_spin.setValue(5)
        form.addWidget(QLabel("文字与码间距（px）："), 5, 0)
        form.addWidget(self.qr_text_margin_spin, 5, 1)

        self.qr_module_color_btn = QPushButton("选择")
        self.qr_module_color_display = QLineEdit("#000000")
        self.qr_module_color_btn.clicked.connect(partial(self._choose_color, self.qr_module_color_display))
        form.addWidget(QLabel("码颜色："), 6, 0)
        form.addWidget(self._hbox(self.qr_module_color_display, self.qr_module_color_btn), 6, 1)

        self.qr_back_color_btn = QPushButton("选择")
        self.qr_back_color_display = QLineEdit("#FFFFFF")
        self.qr_back_color_btn.clicked.connect(partial(self._choose_color, self.qr_back_color_display))
        form.addWidget(QLabel("背景色："), 7, 0)
        form.addWidget(self._hbox(self.qr_back_color_display, self.qr_back_color_btn), 7, 1)

        self.qr_outer_eye_btn = QPushButton("选择")
        self.qr_outer_eye_display = QLineEdit("")
        self.qr_outer_eye_btn.clicked.connect(partial(self._choose_color, self.qr_outer_eye_display))
        form.addWidget(QLabel("外眼颜色（可空）："), 0, 2)
        form.addWidget(self._hbox(self.qr_outer_eye_display, self.qr_outer_eye_btn), 0, 3)

        self.qr_inner_eye_btn = QPushButton("选择")
        self.qr_inner_eye_display = QLineEdit("")
        self.qr_inner_eye_btn.clicked.connect(partial(self._choose_color, self.qr_inner_eye_display))
        form.addWidget(QLabel("内眼颜色（可空）："), 1, 2)
        form.addWidget(self._hbox(self.qr_inner_eye_display, self.qr_inner_eye_btn), 1, 3)

        self.qr_show_text_chk = QCheckBox("显示文字")
        form.addWidget(QLabel("显示文字："), 2, 2)
        form.addWidget(self.qr_show_text_chk, 2, 3)

        self.qr_font_line = QLineEdit("")
        self.qr_font_btn = QPushButton("选择字体")
        self.qr_font_btn.clicked.connect(partial(self.choose_font_file, self.qr_font_line))
        form.addWidget(QLabel("文字字体（可选）："), 3, 2)
        form.addWidget(self._hbox(self.qr_font_line, self.qr_font_btn), 3, 3)

        self.qr_text_pos_combo = QComboBox()
        self.qr_text_pos_combo.addItems(["下方", "上方"])
        form.addWidget(QLabel("文字位置："), 4, 2)
        form.addWidget(self.qr_text_pos_combo, 4, 3)

        self.qr_text_align_combo = QComboBox()
        self.qr_text_align_combo.addItems(["左", "中", "右"])
        form.addWidget(QLabel("对齐方式："), 5, 2)
        form.addWidget(self.qr_text_align_combo, 5, 3)

        self.qr_text_size_spin = QSpinBox()
        self.qr_text_size_spin.setRange(6, 72)
        self.qr_text_size_spin.setValue(12)
        form.addWidget(QLabel("文字大小："), 6, 2)
        form.addWidget(self.qr_text_size_spin, 6, 3)

        self.qr_text_bold_chk = QCheckBox("加粗")
        self.qr_text_italic_chk = QCheckBox("斜体")
        form.addWidget(self._hbox(self.qr_text_bold_chk, self.qr_text_italic_chk), 7, 3)

        self.qr_generate_btn = QPushButton("生成预览图")
        self.qr_generate_btn.clicked.connect(self.on_generate_qr)
        form.addWidget(self.qr_generate_btn, 8, 0, 1, 4)

        layout.addLayout(form)
        layout.addStretch()
        self.qr_tab.setLayout(layout)

    def _build_barcode_tab(self):
        layout = QHBoxLayout()
        form = QGridLayout()
        form.setSpacing(10)

        self.barcode_type_combo = QComboBox()
        types = ["code128", "ean13", "ean8", "upc", "code39", "itf"]
        self.barcode_type_combo.addItems(types)
        form.addWidget(QLabel("条码类型："), 0, 0)
        form.addWidget(self.barcode_type_combo, 0, 1)

        self.bar_width_label = QLabel("条宽（px）：")
        self.bar_width_spin = QSpinBox()
        self.bar_width_spin.setRange(1, 20)
        self.bar_width_spin.setValue(2)
        self.bar_auto_size_chk = QCheckBox("自动尺寸")
        self.bar_auto_size_chk.stateChanged.connect(self._update_ui_for_arrangement)
        form.addWidget(self.bar_width_label, 1, 0)
        form.addWidget(self._hbox(self.bar_width_spin, self.bar_auto_size_chk), 1, 1)

        self.bar_margin_spin = QSpinBox()
        self.bar_margin_spin.setRange(0, 200)
        self.bar_margin_spin.setValue(6)
        form.addWidget(QLabel("左右空白（px）："), 2, 0)
        form.addWidget(self.bar_margin_spin, 2, 1)

        self.bar_height_spin = QSpinBox()
        self.bar_height_spin.setRange(1, 500)
        self.bar_height_spin.setValue(100)
        form.addWidget(QLabel("条码高度（px）："), 3, 0)
        form.addWidget(self.bar_height_spin, 3, 1)

        self.bar_text_margin_spin = QSpinBox()
        self.bar_text_margin_spin.setRange(0, 100)
        self.bar_text_margin_spin.setValue(5)
        form.addWidget(QLabel("文字与码间距（px）："), 4, 0)
        form.addWidget(self.bar_text_margin_spin, 4, 1)

        self.bar_color_display = QLineEdit("#000000")
        self.bar_color_btn = QPushButton("选择")
        self.bar_color_btn.clicked.connect(partial(self._choose_color, self.bar_color_display))
        form.addWidget(QLabel("条码颜色："), 5, 0)
        form.addWidget(self._hbox(self.bar_color_display, self.bar_color_btn), 5, 1)

        self.bar_bg_trans_check = QCheckBox("透明背景")
        form.addWidget(QLabel("透明背景："), 6, 0)
        form.addWidget(self.bar_bg_trans_check, 6, 1)

        self.bar_bg_color_display = QLineEdit("#FFFFFF")
        self.bar_bg_color_btn = QPushButton("选择")
        self.bar_bg_color_btn.clicked.connect(partial(self._choose_color, self.bar_bg_color_display))
        form.addWidget(QLabel("背景色："), 7, 0)
        form.addWidget(self._hbox(self.bar_bg_color_display, self.bar_bg_color_btn), 7, 1)

        self.bar_show_text_chk = QCheckBox("显示文字")
        self.bar_show_text_chk.setChecked(True)
        form.addWidget(QLabel("显示文字："), 0, 2)
        form.addWidget(self.bar_show_text_chk, 0, 3)

        self.bar_font_line = QLineEdit("")
        self.bar_font_btn = QPushButton("选择字体")
        self.bar_font_btn.clicked.connect(partial(self.choose_font_file, self.bar_font_line))
        form.addWidget(QLabel("文字字体（可选）："), 1, 2)
        form.addWidget(self._hbox(self.bar_font_line, self.bar_font_btn), 1, 3)

        self.bar_text_pos_combo = QComboBox()
        self.bar_text_pos_combo.addItems(["下方", "上方"])
        form.addWidget(QLabel("文字位置："), 2, 2)
        form.addWidget(self.bar_text_pos_combo, 2, 3)

        self.bar_text_align_combo = QComboBox()
        self.bar_text_align_combo.addItems(["左", "中", "右"])
        form.addWidget(QLabel("对齐方式："), 3, 2)
        form.addWidget(self.bar_text_align_combo, 3, 3)

        self.bar_text_size_spin = QSpinBox()
        self.bar_text_size_spin.setRange(6, 72)
        self.bar_text_size_spin.setValue(12)
        form.addWidget(QLabel("文字大小："), 4, 2)
        form.addWidget(self.bar_text_size_spin, 4, 3)

        self.bar_text_bold_chk = QCheckBox("加粗")
        self.bar_text_italic_chk = QCheckBox("斜体")
        form.addWidget(self._hbox(self.bar_text_bold_chk, self.bar_text_italic_chk), 5, 3)

        self.bar_generate_btn = QPushButton("生成预览图")
        self.bar_generate_btn.clicked.connect(self.on_generate_barcode)
        form.addWidget(self.bar_generate_btn, 6, 0, 1, 4)

        layout.addLayout(form)
        layout.addStretch()
        self.barcode_tab.setLayout(layout)

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

    def choose_font_file(self, lineedit):
        path, _ = QFileDialog.getOpenFileName(self, "选择字体文件（.ttf/.otf）", "", "字体文件 (*.ttf *.otf);;所有文件 (*)")
        if path:
            lineedit.setText(path)

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
        parts = [p for p in parts if p]
        return parts

    def on_generate_qr(self):
        items = self._parse_input()
        if not items:
            QMessageBox.warning(self, "无数据", "请先在上方输入或上传要生成的数据。")
            return
        preview_items = items[:self.max_display_items]
        v_index = self.qr_version_combo.currentIndex()
        version = None if v_index == 0 else self.qr_version_combo.currentData()
        options = {
            'version': version,
            'error_correction': self.qr_ec_combo.currentText(),
            'out_px': self.qr_size_spin.value(),
            'left_right_padding_px': self.qr_left_right_padding_spin.value(),
            'top_bottom_padding_px': self.qr_top_bottom_padding_spin.value(),
            'module_color': self.qr_module_color_display.text() or "#000000",
            'back_color': self.qr_back_color_display.text() or "#FFFFFF",
            'outer_eye_color': self.qr_outer_eye_display.text() or None,
            'inner_eye_color': self.qr_inner_eye_display.text() or None,
            'show_text': self.qr_show_text_chk.isChecked(),
            'font_path': self.qr_font_line.text() or None,
            'text_pos': 'top' if self.qr_text_pos_combo.currentText() == '上方' else 'bottom',
            'text_align': {'左': 'left', '中': 'center', '右': 'right'}[self.qr_text_align_combo.currentText()],
            'text_margin': self.qr_text_margin_spin.value(),
            'text_size': self.qr_text_size_spin.value(),
            'text_bold': self.qr_text_bold_chk.isChecked(),
            'text_italic': self.qr_text_italic_chk.isChecked()
        }
        auto_size = self.qr_auto_size_chk.isChecked()
        self.clear_display()
        self.start_generation(preview_items, mode='qr', options=options, auto_size=auto_size)

    def on_generate_barcode(self):
        items = self._parse_input()
        if not items:
            QMessageBox.warning(self, "无数据", "请先在上方输入或上传要生成的数据。")
            return
        preview_items = items[:self.max_display_items]
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
        auto_size = self.bar_auto_size_chk.isChecked()
        self.clear_display()
        self.start_generation(preview_items, mode='barcode', options=options, auto_size=auto_size)

    def clear_display(self):
        self.preview_label.clear()
        self.generated_images = []
        self.preview_image = None
        gc.collect()

    def start_generation(self, items, mode, options, auto_size):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(items))
        self.progress_bar.setValue(0)
        self.generator_thread = GeneratorThread(items, mode, options, batch_size=self.batch_size, max_display=self.max_display_items)
        self.generator_thread.image_generated.connect(lambda idx, img, text: self.on_image_generated(idx, img, text, auto_size))
        self.generator_thread.progress.connect(self.on_progress)
        self.generator_thread.finished_all.connect(self.on_generation_finished)
        self.generator_thread.error.connect(self.on_generation_error)
        self.generator_thread.start()

    def on_image_generated(self, idx, pil_img, text, auto_size):
        if idx < self.max_display_items:
            self.generated_images.append((text, pil_img))
        if idx == min(self.max_display_items - 1, len(self._parse_input()) - 1):
            self._render_preview(auto_size)

    def _render_preview(self, auto_size):
        a4_width, a4_height = PAGE_SIZES[self.page_size_combo.currentText()]
        margin = self.qr_left_right_padding_spin.value() if self.tabs.currentWidget() == self.qr_tab else self.bar_margin_spin.value()
        spacing = self.qr_top_bottom_padding_spin.value() if self.tabs.currentWidget() == self.qr_tab else self.bar_text_margin_spin.value()
        codes_per_row = int(self.cols_per_row_combo.currentText()) if self.arrangement_combo.currentText() == "横向排列" else 1
        codes_per_col = 3 if self.arrangement_combo.currentText() == "竖向排列" else 1
        codes_per_page = min(codes_per_row * codes_per_col, self.max_display_items)
        mode = 'qr' if self.tabs.currentWidget() == self.qr_tab else 'barcode'

        # 调整图像大小
        options = {
            'version': None if self.qr_version_combo.currentIndex() == 0 else self.qr_version_combo.currentData(),
            'error_correction': self.qr_ec_combo.currentText(),
            'out_px': self.qr_size_spin.value(),
            'left_right_padding_px': self.qr_left_right_padding_spin.value(),
            'top_bottom_padding_px': self.qr_top_bottom_padding_spin.value(),
            'module_color': self.qr_module_color_display.text() or "#000000",
            'back_color': self.qr_back_color_display.text() or "#FFFFFF",
            'outer_eye_color': self.qr_outer_eye_display.text() or None,
            'inner_eye_color': self.qr_inner_eye_display.text() or None,
            'show_text': self.qr_show_text_chk.isChecked(),
            'font_path': self.qr_font_line.text() or None,
            'text_pos': 'top' if self.qr_text_pos_combo.currentText() == '上方' else 'bottom',
            'text_align': {'左': 'left', '中': 'center', '右': 'right'}[self.qr_text_align_combo.currentText()],
            'text_margin': self.qr_text_margin_spin.value(),
            'text_size': self.qr_text_size_spin.value(),
            'text_bold': self.qr_text_bold_chk.isChecked(),
            'text_italic': self.qr_text_italic_chk.isChecked()
        } if mode == 'qr' else {
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

        if auto_size and self.arrangement_combo.currentText() == "横向排列":
            available_width = (a4_width - 2 * margin - (codes_per_row - 1) * spacing) // codes_per_row
            options['out_px'] = max(100, available_width)
            if mode == 'barcode':
                options['bar_width_px'] = max(1, available_width // 50)  # 假设条宽比例

        # 生成页面图像
        output_img = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
        draw = ImageDraw.Draw(output_img)
        x, y = margin, margin
        max_width = 0
        max_height = 0

        # 重新生成图像以确保使用最新的参数
        self.generated_images = []
        for text in self._parse_input()[:codes_per_page]:
            img = generate_qr_pil(text, **options) if mode == 'qr' else generate_barcode_pil(text, **options)
            self.generated_images.append((text, img))
            max_width = max(max_width, img.width)
            max_height = max(max_height, img.height)

        for i, (text, pil_img) in enumerate(self.generated_images):
            img = pil_img.convert("RGB") if pil_img.mode in ("RGBA", "P") else pil_img
            img = img.resize((max_width, max_height), Image.LANCZOS)
            if self.arrangement_combo.currentText() == "横向排列":
                if x + max_width > a4_width - margin:
                    x = margin
                    y += max_height + spacing
                if y + max_height > a4_height - margin:
                    break
                output_img.paste(img, (x, y))
                draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                x += max_width + spacing
            else:
                if y + max_height > a4_height - margin:
                    break
                output_img.paste(img, (x, y))
                draw.text((x, y + max_height + 10), text[:20], fill=(0, 0, 0))
                y += max_height + spacing
            img.close()
            gc.collect()

        # 缩放预览图像以适应窗口
        scale = min(self.scroll_area.width() / a4_width, self.scroll_area.height() / a4_height, 1.0)
        preview_width = int(a4_width * scale)
        preview_height = int(a4_height * scale)
        output_img = output_img.resize((preview_width, preview_height), Image.LANCZOS)
        self.preview_image = output_img
        pix = pil_image_to_qpixmap(self.preview_image)
        self.preview_label.setPixmap(pix)
        self.preview_label.setFixedSize(preview_width, preview_height)
        gc.collect()

    def _on_thumb_clicked(self, pil_img, text, ev):
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
        if p % 1000 == 0:
            QApplication.processEvents()

    def on_generation_error(self, error_msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "生成错误", error_msg)
        self.generator_thread = None

    def on_generation_finished(self):
        self.progress_bar.setVisible(False)
        self.generator_thread = None

    def export_results(self):
        items = self._parse_input()
        if not items:
            QMessageBox.warning(self, "没有数据", "请先在上方输入或上传要生成的数据。")
            return

        if len(items) > 10000:
            reply = QMessageBox.question(
                self, "数据量警告",
                f"检测到 {len(items)} 条数据，导出可能需要较长时间，预计内存占用 {len(items) * 0.36:.1f} MB。是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        mode = 'qr' if self.tabs.currentWidget() == self.qr_tab else 'barcode'
        options = {
            'version': None if self.qr_version_combo.currentIndex() == 0 else self.qr_version_combo.currentData(),
            'error_correction': self.qr_ec_combo.currentText(),
            'out_px': self.qr_size_spin.value(),
            'left_right_padding_px': self.qr_left_right_padding_spin.value(),
            'top_bottom_padding_px': self.qr_top_bottom_padding_spin.value(),
            'module_color': self.qr_module_color_display.text() or "#000000",
            'back_color': self.qr_back_color_display.text() or "#FFFFFF",
            'outer_eye_color': self.qr_outer_eye_display.text() or None,
            'inner_eye_color': self.qr_inner_eye_display.text() or None,
            'show_text': self.qr_show_text_chk.isChecked(),
            'font_path': self.qr_font_line.text() or None,
            'text_pos': 'top' if self.qr_text_pos_combo.currentText() == '上方' else 'bottom',
            'text_align': {'左': 'left', '中': 'center', '右': 'right'}[self.qr_text_align_combo.currentText()],
            'text_margin': self.qr_text_margin_spin.value(),
            'text_size': self.qr_text_size_spin.value(),
            'text_bold': self.qr_text_bold_chk.isChecked(),
            'text_italic': self.qr_text_italic_chk.isChecked()
        } if mode == 'qr' else {
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
        auto_size = self.qr_auto_size_chk.isChecked() if mode == 'qr' else self.bar_auto_size_chk.isChecked()
        fmt = self.export_format_combo.currentText()
        arrangement = self.arrangement_combo.currentText()
        cols_per_row = int(self.cols_per_row_combo.currentText())
        page_size = self.page_size_combo.currentText()

        if fmt == "PDF":
            path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", "batch_codes.pdf", "PDF 文件 (*.pdf)")
            if not path:
                return
        else:
            path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
            if not path:
                return

        self.setEnabled(False)

        self.progress_dialog = ProgressDialog(len(items), self)
        self.export_thread = ExportThread(items, mode, options, fmt, arrangement, cols_per_row, path, page_size, auto_size, self)
        self.progress_dialog.cancel_btn.clicked.connect(self.cancel_export)
        self.export_thread.progress.connect(self.progress_dialog.update_progress)
        self.export_thread.status.connect(self.progress_dialog.update_status)
        self.export_thread.finished.connect(self.on_export_finished)
        self.export_thread.error.connect(self.on_export_error)
        self.export_thread.start()
        self.progress_dialog.exec()

    def cancel_export(self):
        if self.export_thread:
            self.export_thread.stop()
            self.export_thread.wait()
            self.export_thread = None
        self.progress_dialog.close()
        self.setEnabled(True)
        QMessageBox.information(self, "导出取消", "导出过程已取消，临时文件已清理。")

    def on_export_finished(self, message):
        self.progress_dialog.close()
        self.setEnabled(True)
        self.export_thread = None
        if message:
            QMessageBox.information(self, "导出成功", message)
        gc.collect()

    def on_export_error(self, error_msg):
        self.progress_dialog.close()
        self.setEnabled(True)
        self.export_thread = None
        QMessageBox.critical(self, "导出失败", error_msg)
        gc.collect()

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()