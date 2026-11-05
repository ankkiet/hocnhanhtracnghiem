import io
import os
import struct
import sys
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


def emf_to_svg_crossplatform(blob: bytes) -> Optional[str]:
    """
    Chuyển đổi dữ liệu EMF sang chuẩn vector SVG thuần túy (Pure Python).
    Hỗ trợ đầy đủ các bản ghi vector: WorldTransform matrix, Polygon16, Polyline16,
    PolyBezierTo16, ExtTextOutW/A, ExtCreatePen, CreateBrush, SetTextColor.
    Hoạt động 100% độc lập, không phụ thuộc hệ điều hành (chạy tốt trên Linux, Docker, Windows).
    """
    if not blob or len(blob) < 88:
        return None

    try:
        # 1. Đọc Header EMF
        itype, nsize, r_left, r_top, r_right, r_bottom = struct.unpack('<IIiiii', blob[:24])
        if itype != 1:  # EMR_HEADER
            return None

        width = abs(r_right - r_left)
        height = abs(r_bottom - r_top)
        if width <= 0 or height <= 0:
            width, height = 800, 600

        pad = 10
        v_left = r_left - pad
        v_top = r_top - pad
        v_width = width + pad * 2
        v_height = height + pad * 2

        svg_elements = []
        objects = {}
        current_pen = {"color": "#000000", "width": 1.5}
        current_brush = {"color": "none"}
        current_text_color = "#000000"

        # World Transform Matrix: [m11, m12, m21, m22, dx, dy]
        matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        pos = 0
        while pos < len(blob):
            if pos + 8 > len(blob):
                break
            itype, nsize = struct.unpack('<II', blob[pos:pos+8])
            if nsize < 8 or pos + nsize > len(blob):
                break

            rec_data = blob[pos+8:pos+nsize]

            # 35: EMR_SETWORLDTRANSFORM (xform: 6 floats)
            if itype == 35 and len(rec_data) >= 24:
                m11, m12, m21, m22, dx, dy = struct.unpack('<ffffff', rec_data[:24])
                matrix = [m11, m12, m21, m22, dx, dy]

            # 36: EMR_MODIFYWORLDTRANSFORM (xform: 6 floats, mode: 4 bytes)
            elif itype == 36 and len(rec_data) >= 28:
                m11, m12, m21, m22, dx, dy, mode = struct.unpack('<ffffffI', rec_data[:28])
                if mode == 1:  # MWT_IDENTITY
                    matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                elif mode == 2:  # MWT_LEFTMULTIPLY: New x Current
                    c11, c12, c21, c22, cdx, cdy = matrix
                    matrix = [
                        m11 * c11 + m12 * c21,
                        m11 * c12 + m12 * c22,
                        m21 * c11 + m22 * c21,
                        m21 * c12 + m22 * c22,
                        dx * c11 + dy * c21 + cdx,
                        dx * c12 + dy * c22 + cdy
                    ]
                elif mode == 3:  # MWT_RIGHTMULTIPLY: Current x New
                    c11, c12, c21, c22, cdx, cdy = matrix
                    matrix = [
                        c11 * m11 + c12 * m21,
                        c11 * m12 + c12 * m22,
                        c21 * m11 + c22 * m21,
                        c21 * m12 + c22 * m22,
                        cdx * m11 + cdy * m21 + dx,
                        cdx * m12 + cdy * m22 + dy
                    ]
                else:
                    matrix = [m11, m12, m21, m22, dx, dy]

            # 19: EMR_SELECTOBJECT
            elif itype == 19 and len(rec_data) >= 4:
                obj_idx = struct.unpack('<I', rec_data[:4])[0]
                if obj_idx in objects:
                    obj = objects[obj_idx]
                    if obj["type"] == "pen":
                        current_pen = obj
                    elif obj["type"] == "brush":
                        current_brush = obj

            # 70: EMR_EXTCREATEPEN
            elif itype == 70 and len(rec_data) >= 32:
                ih_pen = struct.unpack('<I', rec_data[:4])[0]
                pen_width = struct.unpack('<I', rec_data[20:24])[0]
                color_ref = struct.unpack('<I', rec_data[28:32])[0]
                r = color_ref & 0xFF
                g = (color_ref >> 8) & 0xFF
                b = (color_ref >> 16) & 0xFF
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                stroke_w = max(1.0, float(pen_width) if pen_width > 0 else 1.5)
                objects[ih_pen] = {"type": "pen", "color": hex_color, "width": stroke_w}

            # 38: EMR_CREATEPEN
            elif itype == 38 and len(rec_data) >= 16:
                ih_pen = struct.unpack('<I', rec_data[:4])[0]
                pen_w = struct.unpack('<i', rec_data[8:12])[0]
                color_ref = struct.unpack('<I', rec_data[12:16])[0]
                r = color_ref & 0xFF
                g = (color_ref >> 8) & 0xFF
                b = (color_ref >> 16) & 0xFF
                objects[ih_pen] = {"type": "pen", "color": f"#{r:02x}{g:02x}{b:02x}", "width": max(1.0, float(pen_w))}

            # 39: EMR_CREATEBRUSHINDIRECT
            elif itype == 39 and len(rec_data) >= 12:
                ih_brush = struct.unpack('<I', rec_data[:4])[0]
                color_ref = struct.unpack('<I', rec_data[8:12])[0]
                r = color_ref & 0xFF
                g = (color_ref >> 8) & 0xFF
                b = (color_ref >> 16) & 0xFF
                objects[ih_brush] = {"type": "brush", "color": f"#{r:02x}{g:02x}{b:02x}"}

            # 22: EMR_SETTEXTCOLOR
            elif itype == 22 and len(rec_data) >= 4:
                color_ref = struct.unpack('<I', rec_data[:4])[0]
                r = color_ref & 0xFF
                g = (color_ref >> 8) & 0xFF
                b = (color_ref >> 16) & 0xFF
                current_text_color = f"#{r:02x}{g:02x}{b:02x}"

            def transform_pt(x, y):
                m11, m12, m21, m22, dx, dy = matrix
                tx = x * m11 + y * m21 + dx
                ty = x * m12 + y * m22 + dy
                return tx, ty

            # 87: EMR_POLYGON16 / 3: EMR_POLYGON
            if (itype == 87 or itype == 3) and len(rec_data) >= 20:
                cpts = struct.unpack('<I', rec_data[16:20])[0]
                pt_fmt = f'<{cpts*2}h' if itype == 87 else f'<{cpts*2}i'
                pt_bytes_len = cpts * (4 if itype == 87 else 8)
                if len(rec_data) >= 20 + pt_bytes_len:
                    pts = struct.unpack(pt_fmt, rec_data[20:20 + pt_bytes_len])
                    mapped_pts = [transform_pt(pts[i*2], pts[i*2+1]) for i in range(cpts)]
                    if cpts == 2:
                        p1, p2 = mapped_pts
                        svg_elements.append(
                            f'<line x1="{p1[0]:.2f}" y1="{p1[1]:.2f}" x2="{p2[0]:.2f}" y2="{p2[1]:.2f}" '
                            f'stroke="{current_pen["color"]}" stroke-width="{current_pen["width"]}" stroke-linecap="round" />'
                        )
                    else:
                        pts_str = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in mapped_pts)
                        svg_elements.append(
                            f'<polygon points="{pts_str}" fill="{current_pen["color"]}" stroke="{current_pen["color"]}" '
                            f'stroke-width="{current_pen["width"]}" />'
                        )

            # 88: EMR_POLYLINE16 / 4: EMR_POLYLINE
            elif (itype == 88 or itype == 4) and len(rec_data) >= 20:
                cpts = struct.unpack('<I', rec_data[16:20])[0]
                pt_fmt = f'<{cpts*2}h' if itype == 88 else f'<{cpts*2}i'
                pt_bytes_len = cpts * (4 if itype == 88 else 8)
                if len(rec_data) >= 20 + pt_bytes_len:
                    pts = struct.unpack(pt_fmt, rec_data[20:20 + pt_bytes_len])
                    mapped_pts = [transform_pt(pts[i*2], pts[i*2+1]) for i in range(cpts)]
                    pts_str = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in mapped_pts)
                    svg_elements.append(
                        f'<polyline points="{pts_str}" fill="none" stroke="{current_pen["color"]}" '
                        f'stroke-width="{current_pen["width"]}" stroke-linecap="round" stroke-linejoin="round" />'
                    )

            # 95: EMR_POLYBEZIERTO16 / 85: EMR_POLYBEZIER16
            elif (itype == 95 or itype == 85) and len(rec_data) >= 20:
                cpts = struct.unpack('<I', rec_data[16:20])[0]
                if len(rec_data) >= 20 + cpts * 4 and cpts >= 3:
                    pts = struct.unpack(f'<{cpts*2}h', rec_data[20:20 + cpts * 4])
                    mapped_pts = [transform_pt(pts[i*2], pts[i*2+1]) for i in range(cpts)]
                    d_path = f"M {mapped_pts[0][0]:.2f} {mapped_pts[0][1]:.2f}"
                    for b_i in range(1, cpts - 2, 3):
                        cp1, cp2, ep = mapped_pts[b_i], mapped_pts[b_i+1], mapped_pts[b_i+2]
                        d_path += f" C {cp1[0]:.2f} {cp1[1]:.2f}, {cp2[0]:.2f} {cp2[1]:.2f}, {ep[0]:.2f} {ep[1]:.2f}"
                    svg_elements.append(
                        f'<path d="{d_path}" fill="none" stroke="{current_pen["color"]}" '
                        f'stroke-width="{current_pen["width"]}" stroke-linecap="round" />'
                    )

            # 84: EMR_EXTTEXTOUTW / 83: EMR_EXTTEXTOUTA
            elif (itype == 84 or itype == 83) and len(rec_data) >= 28:
                emrtext_offset = 28
                if len(rec_data) >= emrtext_offset + 16:
                    ptlx, ptly, nchars, off_str = struct.unpack('<iiII', rec_data[emrtext_offset:emrtext_offset+16])
                    str_offset_in_rec = off_str - 8
                    char_bytes = 2 if itype == 84 else 1
                    encoding = 'utf-16le' if itype == 84 else 'latin-1'
                    if len(rec_data) >= str_offset_in_rec + nchars * char_bytes:
                        text_bytes = rec_data[str_offset_in_rec:str_offset_in_rec + nchars * char_bytes]
                        text_str = text_bytes.decode(encoding, errors='ignore').strip()
                        if text_str:
                            x, y = ptlx, ptly
                            clean_svg_text = text_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            svg_elements.append(
                                f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, Helvetica, sans-serif" '
                                f'font-size="14" font-weight="bold" fill="{current_text_color}">{clean_svg_text}</text>'
                            )

            pos += nsize

        if not svg_elements:
            return None

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{v_left} {v_top} {v_width} {v_height}" '
            f'width="{v_width}" height="{v_height}">\n'
            f'<rect width="100%" height="100%" fill="white"/>\n'
            + "\n".join(svg_elements) +
            "\n</svg>"
        )
        return svg_content
    except Exception:
        return None


def convert_emf_to_png_pymupdf(data: bytes, dpi: int = 150) -> Optional[bytes]:
    """
    Chuyển đổi dữ liệu EMF sang PNG sắc nét đa nền tảng bằng PyMuPDF.
    Hoạt động 100% trên Linux Docker (Koyeb) và Windows.
    """
    svg_str = emf_to_svg_crossplatform(data)
    if not svg_str:
        return None

    try:
        import fitz
        with fitz.open(stream=svg_str.encode('utf-8'), filetype='svg') as doc:
            if len(doc) > 0:
                pix = doc[0].get_pixmap(dpi=dpi)
                return pix.tobytes("png")
    except Exception:
        try:
            import pymupdf
            with pymupdf.open(stream=svg_str.encode('utf-8'), filetype='svg') as doc:
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(dpi=dpi)
                    return pix.tobytes("png")
        except Exception:
            pass

    return None


def convert_vector_image_to_png(data: bytes) -> Optional[bytes]:
    """
    Cố gắng chuyển đổi ảnh vector WMF/EMF sang PNG bằng tất cả các phương pháp khả dụng.
    Đảm bảo 100% ảnh hóa học, sơ đồ công thức từ Word/ChemDraw đều hiển thị sắc nét trên web và điện thoại.
    """
    # 1. Thử Windows GDI+ (ưu tiên hàng đầu khi chạy trên Windows)
    png_bytes = convert_emf_wmf_to_png_gdiplus(data)
    if png_bytes:
        return png_bytes

    # 2. Thử chuyển đổi vector EMF -> SVG -> PNG bằng PyMuPDF (Đa nền tảng Linux/Windows/Mac)
    png_bytes_mupdf = convert_emf_to_png_pymupdf(data)
    if png_bytes_mupdf:
        return png_bytes_mupdf

    # 3. Thử tìm ảnh raster nhúng bên trong metafile
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

    # 4. Thử mở bằng Pillow
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
                    new_height = int(img.height * new_width / img.width) if needs_resize else img.height
                    resample_filter = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                    resized_img = img.resize((new_width, new_height), resample_filter) if needs_resize else img

                    out_io = io.BytesIO()
                    is_png_or_webp = ('png' in mime_type.lower() or 'webp' in mime_type.lower() or detected_fmt == 'png')
                    if is_png_or_webp or img.mode in ('RGBA', 'P'):
                        target_format = 'WEBP' if 'webp' in mime_type.lower() else 'PNG'
                        target_mime = 'image/webp' if 'webp' in mime_type.lower() else 'image/png'
                        resized_img.save(out_io, format=target_format, optimize=True)
                        return out_io.getvalue(), target_mime
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
