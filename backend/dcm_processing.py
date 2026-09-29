import base64
from io import BytesIO

import numpy as np
import pydicom
from PIL import Image, ImageDraw

OVERLAY_GROUP_MIN = 0x6000
OVERLAY_GROUP_MAX = 0x60FF


def decode_dicom(raw: bytes) -> pydicom.Dataset:
    try:
        return pydicom.dcmread(BytesIO(raw), force=True)
    except Exception as exc:
        raise ValueError(f"Не удалось прочитать DICOM-файл: {exc}") from exc


def _scalar(ds, tag, default=None):
    element = ds.get(tag)
    if element is None:
        return default
    value = element.value
    if isinstance(value, (list, tuple, set)):
        return default
    return value


def _text(ds, tag):
    element = ds.get(tag)
    if element is None:
        return None
    try:
        value = element.value
        if isinstance(value, (list, tuple, set)):
            return " / ".join(str(v) for v in value)
        return str(value)
    except Exception:
        return None


def _extract_frame_array(ds):
    try:
        array = ds.pixel_array
    except Exception as exc:
        raise ValueError(
            "Не удалось декодировать пиксельные данные DICOM. "
            f"Для сжатых форматов (JPEG/JP2K) может потребоваться pylibjpeg. ({exc})"
        ) from exc
    if array.ndim > 2:
        array = array[array.shape[0] // 2]
    return np.asarray(array, dtype=np.float64)


def _map_to_uint8(pixel, ds):
    low = high = None
    window_center = _scalar(ds, (0x0028, 0x1050))
    window_width = _scalar(ds, (0x0028, 0x1051))
    if window_center is not None and window_width is not None:
        try:
            low = float(window_center) - float(window_width) / 2.0
            high = float(window_center) + float(window_width) / 2.0
        except (TypeError, ValueError):
            low = high = None
    if low is None or high is None or high <= low:
        low, high = np.percentile(pixel, (1.0, 99.0))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low, high = float(pixel.min()), float(pixel.max())
        if high <= low:
            high = low + 1e-6
    return np.clip((pixel - low) / (high - low) * 255.0, 0.0, 255.0).astype(np.uint8)


def _iter_overlay_points(ds, shape):
    rows_total, cols_total = shape
    for group in range(OVERLAY_GROUP_MIN, OVERLAY_GROUP_MAX):
        data_tag = (group, 0x3000)
        if data_tag not in ds:
            continue
        try:
            rows = int(_scalar(ds, (group, 0x0010), 0) or 0)
            cols = int(_scalar(ds, (group, 0x0011), 0) or 0)
            bits_allocated = int(_scalar(ds, (group, 0x0100), 1) or 1)
            frames = int(_scalar(ds, (group, 0x0015), 1) or 1)
            if bits_allocated != 1 or frames < 1 or rows <= 0 or cols <= 0:
                continue
            origin_row, origin_col = 1, 1
            origin_element = ds.get((group, 0x0050))
            if origin_element is not None:
                values = origin_element.value
                if isinstance(values, (list, tuple)) and len(values) >= 2:
                    origin_row, origin_col = int(values[0]), int(values[1])
            overlay_type = str(_scalar(ds, (group, 0x0020), "G") or "G").upper()
            raw = ds[data_tag].value
            if not raw:
                continue
            if ds[data_tag].VR == "OW":
                words = np.frombuffer(raw, dtype="<u2")
                little_endian = words.view(np.uint8)
            else:
                little_endian = np.frombuffer(raw, dtype=np.uint8)
            bits = np.unpackbits(little_endian, bitorder="little")
            need = rows * cols
            if bits.size < need:
                bits = np.pad(bits, (0, need - bits.size))
            plane = bits[:need].reshape((rows, cols))
            ys, xs = np.nonzero(plane)
            if ys.size == 0:
                continue
            ys = ys.astype(np.int64) + (origin_row - 1)
            xs = xs.astype(np.int64) + (origin_col - 1)
            visible = (ys >= 0) & (ys < rows_total) & (xs >= 0) & (xs < cols_total)
            ys, xs = ys[visible], xs[visible]
            if ys.size == 0:
                continue
            if overlay_type == "G":
                color = (255, 0, 0)
            elif overlay_type == "R":
                color = (0, 255, 0)
            else:
                color = (0, 200, 255)
            yield ys, xs, color
        except Exception:
            continue


def dataset_to_preview_image(ds, include_overlays=True):
    """Возвращает RGB PIL.Image, которую видит MedGemma."""
    mono_chrome1 = (
        str(_scalar(ds, (0x0028, 0x0004), "")) or ""
    ).upper() == "MONOCHROME1"

    pixel = _extract_frame_array(ds)
    slope = float(_scalar(ds, (0x0028, 0x1053), 1.0) or 1.0)
    intercept = float(_scalar(ds, (0x0028, 0x1052), 0.0) or 0.0)
    pixel = pixel * slope + intercept

    image = _map_to_uint8(pixel, ds)
    if mono_chrome1:
        image = 255 - image

    pil_image = Image.fromarray(image, mode="L").convert("RGB")
    if include_overlays:
        draw = ImageDraw.Draw(pil_image)
        for ys, xs, color in _iter_overlay_points(ds, image.shape):
            draw.point(list(zip(xs.tolist(), ys.tolist())), fill=color)
    return pil_image


def image_to_base64(pil_image, format="PNG"):
    buffer = BytesIO()
    pil_image.save(buffer, format=format, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def dataset_to_preview_base64(ds, include_overlays=True):
    return image_to_base64(dataset_to_preview_image(ds, include_overlays=include_overlays))


def extract_metadata(ds):
    rows = ds.get("Rows")
    columns = ds.get("Columns")
    resolution = None
    if rows is not None and columns is not None:
        try:
            resolution = f"{int(rows)} x {int(columns)}"
        except (TypeError, ValueError):
            resolution = None
    return {
        "manufacturer": _text(ds, (0x0008, 0x0070)),
        "model": _text(ds, (0x0008, 0x1090)),
        "body_part": _text(ds, (0x0018, 0x0015)),
        "modality": _text(ds, (0x0008, 0x0060)),
        "study_description": _text(ds, (0x0008, 0x1030)),
        "protocol_name": _text(ds, (0x0018, 0x1030)),
        "view_position": _text(ds, (0x0018, 0x5101)),
        "image_type": _text(ds, (0x0008, 0x0008)),
        "series_description": _text(ds, (0x0008, 0x103E)),
        "resolution": resolution,
    }