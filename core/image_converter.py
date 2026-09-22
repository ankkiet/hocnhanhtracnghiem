import os
import sys
import io
import tempfile
from typing import Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

# Mã định danh PNG Encoder trong Windows GDI+
# CLSID = {557CF406-1A04-11D3-9A73-0000F81EF32E}
CLSID_PNG = None
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [
            ('Data1', wintypes.DWORD),
            ('Data2', wintypes.WORD),
            ('Data3', wintypes.WORD),
            ('Data4', ctypes.c_ubyte * 8)
        ]

    CLSID_PNG = _GUID(
        0x557cf406, 0x1a04, 0x11d3,
        (ctypes.c_ubyte * 8)(0x9a, 0x73, 0x00, 0x00, 0xf8, 0x1e, 0xf3, 0x2e)
    )

    class _GdiplusStartupInput(ctypes.Structure):
        _fields_ = [
            ('GdiplusVersion', wintypes.UINT),
            ('DebugEventCallback', ctypes.c_void_p),
            ('SuppressBackgroundThread', wintypes.BOOL),
            ('SuppressExternalCodecs', wintypes.BOOL)
        ]


def detect_image_format(data: bytes) -> str:
    """
    Nhận diện định dạng ảnh dựa trên magic bytes nhị phân.
    """
    if not data or len(data) < 4:
        return "unknown"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"\x49\x49\x2a\x00") or data.startswith(b"\x4d\x4d\x00\x2a"):
        return "tiff"
    if data[:4] == b"\x01\x00\x00\x00" or b" EMF" in data[:40]:
        return "emf"
    if data[:4] in [b"\xd7\xcd\xc6\x9a", b"\x01\x00\x09\x00"]:
        return "wmf"
    if b"<svg" in data[:250] or (b"<?xml" in data[:50] and b"<svg" in data[:500]):
        return "svg"
    return "unknown"


def convert_emf_wmf_to_png_gdiplus(data: bytes) -> Optional[bytes]:
    """
    Chuyển đổi dữ liệu nhị phân WMF/EMF sang định dạng PNG chuẩn bằng Windows GDI+.
    Hỗ trợ kết xuất đồ họa vector sắc nét (MathType, biểu đồ Word) với độ tin cậy 100% trên Windows.
    """
    if sys.platform != "win32" or CLSID_PNG is None:
        return None

    temp_in = None
    temp_out = None
    token = ctypes.c_ulong()
    try:
        gdiplus = ctypes.windll.gdiplus
        startup_in = _GdiplusStartupInput(1, None, False, False)
        status = gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup_in), None)
        if status != 0:
            return None

        # Xác định phần mở rộng tạm thời
        is_emf = data[:4] == b'\x01\x00\x00\x00' or b' EMF' in data[:40]
        ext = '.emf' if is_emf else '.wmf'

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            temp_in = f.name

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_out = f.name

        p_image = ctypes.c_void_p()
        load_status = gdiplus.GdipLoadImageFromFile(ctypes.c_wchar_p(temp_in), ctypes.byref(p_image))
        if load_status != 0 or not p_image:
            gdiplus.GdiplusShutdown(token)
            return None

        save_status = gdiplus.GdipSaveImageToFile(p_image, ctypes.c_wchar_p(temp_out), ctypes.byref(CLSID_PNG), None)
        gdiplus.GdipDisposeImage(p_image)
        gdiplus.GdiplusShutdown(token)

        if save_status == 0 and os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
            with open(temp_out, 'rb') as f:
                return f.read()
    except Exception as e:
        print(f"[CẢNH BÁO] GDI+ không thể chuyển đổi EMF/WMF: {e}")
    finally:
        if temp_in and os.path.exists(temp_in):
            try: os.remove(temp_in)
            except Exception: pass
        if temp_out and os.path.exists(temp_out):
            try: os.remove(temp_out)
            except Exception: pass

    return None


def extract_embedded_raster_from_metafile(data: bytes) -> Optional[Tuple[bytes, str]]:
    """
    Quét tìm dữ liệu ảnh raster (PNG, JPEG, BMP) được nhúng bên trong khối WMF/EMF.
    """
    # Tìm PNG nhúng
    png_idx = data.find(b'\x89PNG\r\n\x1a\n')
    if png_idx != -1:
        iend_idx = data.find(b'IEND', png_idx)
        if iend_idx != -1:
            png_bytes = data[png_idx:iend_idx + 8]
            return png_bytes, "image/png"

    # Tìm JPEG nhúng
    jpg_idx = data.find(b'\xff\xd8\xff')
    if jpg_idx != -1:
        eoi_idx = data.find(b'\xff\xd9', jpg_idx)
        if eoi_idx != -1:
            jpg_bytes = data[jpg_idx:eoi_idx + 2]
            return jpg_bytes, "image/jpeg"

    return None


def convert_vector_image_to_png(data: bytes) -> Optional[bytes]:
    """
    Cố gắng chuyển đổi ảnh vector WMF/EMF sang PNG bằng tất cả các phương pháp khả dụng.
    """
    # 1. Thử Windows GDI+ (ưu tiên hàng đầu, chất lượng cao nhất)
    png_bytes = convert_emf_wmf_to_png_gdiplus(data)
    if png_bytes:
        return png_bytes

    # 2. Thử tìm ảnh raster nhúng bên trong metafile
    extracted = extract_embedded_raster_from_metafile(data)
    if extracted:
        img_bytes, mime = extracted
        if mime == "image/png":
            return img_bytes
        if Image is not None:
            try:
                with Image.open(io.BytesIO(img_bytes)) as img:
                    out = io.BytesIO()
                    img.save(out, format="PNG")
                    return out.getvalue()
            except Exception:
                return img_bytes

    # 3. Thử mở bằng Pillow
    if Image is not None:
        try:
            with Image.open(io.BytesIO(data)) as img:
                out = io.BytesIO()
                img.save(out, format="PNG")
                return out.getvalue()
        except Exception:
            pass

    return None


def process_image_blob(blob: bytes, mime_type: str, max_width: int = 800) -> Tuple[bytes, str]:
    """
    Chuẩn hóa dữ liệu ảnh tải lên:
    - Tự động chuyển đổi WMF/EMF sang PNG sắc nét.
    - Tối ưu hóa kích thước ảnh raster nếu kích thước vượt quá max_width.
    - Không bao giờ ném Exception gây dừng tiến trình phân tích.
    """
    if not blob:
        return None, ""

    detected_fmt = detect_image_format(blob)
    is_wmf_emf = (
        mime_type in ['image/x-emf', 'image/x-wmf', 'image/emf', 'image/wmf'] or
        detected_fmt in ['emf', 'wmf'] or
        blob[:4] == b'\x01\x00\x00\x00' or  # EMF Header
        blob[:4] in [b'\xd7\xcd\xc6\x9a', b'\x01\x00\x09\x00']  # WMF Header
    )

    # Từ chối các tệp nhị phân không phải ảnh (ví dụ OLEObject .bin, macro, XML rác)
    if not is_wmf_emf and detected_fmt == "unknown" and not mime_type.startswith("image/"):
        return None, ""

    if is_wmf_emf:
        converted = convert_vector_image_to_png(blob)
        if converted:
            return converted, "image/png"
        return blob, mime_type

    # Xử lý tối ưu hóa kích thước ảnh raster bằng Pillow
    if Image is not None and mime_type not in ['image/svg+xml'] and detected_fmt != 'svg':
        try:
            with Image.open(io.BytesIO(blob)) as img:
                # Bỏ qua các ảnh spacer siêu nhỏ (<= 2x2 px)
                if img.width <= 2 and img.height <= 2:
                    return None, ""

                needs_resize = img.width > max_width
                if needs_resize or mime_type in ['image/bmp', 'image/tiff']:
                    new_width = min(img.width, max_width)
                    new_height = int(new_width * img.height / max_width) if needs_resize else img.height
                    resample_filter = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                    resized_img = img.resize((new_width, new_height), resample_filter) if needs_resize else img

                    out_io = io.BytesIO()
                    if img.mode in ('RGBA', 'P') and ('png' in mime_type.lower() or 'webp' in mime_type.lower() or detected_fmt == 'png'):
                        resized_img.save(out_io, format='PNG', optimize=True)
                        return out_io.getvalue(), 'image/png'
                    else:
                        if resized_img.mode in ('RGBA', 'P'):
                            resized_img = resized_img.convert('RGB')
                        resized_img.save(out_io, format='JPEG', quality=85, optimize=True)
                        return out_io.getvalue(), 'image/jpeg'
        except Exception:
            # Nếu Pillow không đọc được mà cũng không phải format ảnh đã biết -> từ chối
            if detected_fmt == "unknown":
                return None, ""

    return blob, mime_type
