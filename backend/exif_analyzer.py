"""
EXIF 解析模块 — 用 Pillow 读取照片的拍摄参数。
"""
from io import BytesIO
from PIL import Image

# EXIF tag id → 标准化字段名映射
_EXIF_TAGS = {
    33437: "aperture",       # FNumber
    37378: "aperture_apx",   # ApertureValue (APEX)
    33434: "shutter_speed",  # ExposureTime
    37377: "shutter_apx",    # ShutterSpeedValue (APEX)
    34855: "iso",            # ISOSpeedRatings
    8832:   "iso_alt",       # RecommendedExposureIndex
    37386: "focal_length",   # FocalLength
    37385: "focal_35mm",     # FocalLengthIn35mmFilm
    272:   "camera_model",   # Model
    271:   "camera_make",    # Make
    42036: "lens_model",     # LensModel
    36867: "datetime_orig",  # DateTimeOriginal
    306:   "datetime",       # DateTime
}

_WANTED_TAGS = frozenset(_EXIF_TAGS.keys())


def _map_exif(raw: dict) -> dict:
    """将原始 EXIF tag-id dict 映射为标准化 key dict。"""
    result = {}
    for tag_id, key in _EXIF_TAGS.items():
        val = raw.get(tag_id)
        if val is None:
            continue
        # 字节串转字符串
        if isinstance(val, bytes):
            try:
                val = val.decode("utf-8").strip("\x00")
            except UnicodeDecodeError:
                continue
        # 元组值取均值（如 GPS 相关, 但不在此处处理）
        if isinstance(val, tuple):
            val = val[0] if len(val) == 1 else val
        result[key] = val
    return result


def _format_shutter(raw: float | str | None) -> str | None:
    """将快门速度格式化为可读字符串（如 '1/250s'）。"""
    if raw is None:
        return None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return None
    if val >= 1:
        return f"{val:.1f}s"
    denominator = int(round(1 / val))
    return f"1/{denominator}s"


def _format_aperture(raw: float | str | None) -> str | None:
    """格式化光圈值（如 'f/2.8'）。"""
    if raw is None:
        return None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return None
    return f"f/{val:.1f}"


def _format_focal(raw: float | str | None) -> str | None:
    """格式化焦距（如 '50mm'）。"""
    if raw is None:
        return None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return None
    return f"{int(round(val))}mm"


def parse_exif(image_bytes: bytes) -> dict:
    """解析图片 EXIF 数据，返回标准化参数字典。

    Returns:
        {
            "aperture": "f/2.8",
            "shutter_speed": "1/250s",
            "iso": 400,
            "focal_length": "50mm",
            "camera": "Sony A7M4",
            "lens": "FE 24-70mm F2.8 GM II",
            "datetime": "2025-05-26 14:30:00",
        }
        无 EXIF 数据时返回空字典。
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        raw = img._getexif()
        if raw is None:
            return {}
        mapped = _map_exif(raw)
    except Exception:
        return {}

    # 获取实际字段值（fallback 链）
    iso = mapped.get("iso") or mapped.get("iso_alt")
    aperture = mapped.get("aperture") or mapped.get("aperture_apx")
    shutter = mapped.get("shutter_speed") or mapped.get("shutter_apx")
    focal = mapped.get("focal_length")
    camera = mapped.get("camera_model")
    if not camera:
        make = mapped.get("camera_make")
        model = mapped.get("camera_model")
        camera = f"{make} {model}".strip() if make else None
    else:
        # 有相机型号时追加厂商名
        make = mapped.get("camera_make")
        if make and make not in str(camera):
            camera = f"{make} {camera}"
    lens = mapped.get("lens_model")
    dt = mapped.get("datetime_orig") or mapped.get("datetime")

    result = {}
    if aperture:
        result["aperture"] = _format_aperture(aperture)
    if shutter:
        result["shutter_speed"] = _format_shutter(shutter)
    if iso:
        try:
            result["iso"] = int(iso)
        except (ValueError, TypeError):
            pass
    if focal:
        result["focal_length"] = _format_focal(focal)
    if camera:
        result["camera"] = camera
    if lens:
        result["lens"] = lens
    if dt:
        result["datetime"] = str(dt)

    return result


def analyze_params(photos_data: list[dict]) -> str:
    """聚合多张照片的 EXIF 数据，生成参数规律摘要文本。

    Args:
        photos_data: [{filename, exif: {aperture, shutter_speed, iso, focal_length, camera, lens, datetime}}]

    Returns:
        可读的参数摘要文本，用于拼接 AI prompt。
    """
    if not photos_data:
        return "无照片数据"

    lines = []
    for i, p in enumerate(photos_data):
        exif = p.get("exif", {})
        if not exif:
            lines.append(f"照片 {i+1} ({p.get('filename', '未知')}): 无 EXIF 数据")
            continue
        parts = []
        for key, label in [
            ("aperture", "光圈"), ("shutter_speed", "快门"),
            ("iso", "ISO"), ("focal_length", "焦距"),
            ("camera", "相机"), ("lens", "镜头"),
        ]:
            if key in exif:
                parts.append(f"{label}: {exif[key]}")
        header = f"照片 {i+1} ({p.get('filename', '未知')})"
        if "datetime" in exif:
            header += f" [{exif['datetime']}]"
        lines.append(header)
        lines.append("  " + ", ".join(parts))

    return "\n".join(lines)
