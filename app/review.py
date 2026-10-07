"""Geracao de imagens (JPEG redimensionado) para a tela de selecao."""
import io
import os
import threading
from collections import OrderedDict

from PIL import Image, ImageOps

from . import core

_cache = OrderedDict()
_lock = threading.Lock()
_MAX_CACHE = 40


def _abrir(path):
    if path.lower().endswith(core.EXT_RAW):
        import rawpy
        with rawpy.imread(path) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    img = Image.open(io.BytesIO(thumb.data))
                    img.load()
                    if max(img.size) >= 1600:
                        return ImageOps.exif_transpose(img)
            except Exception:
                pass
            rgb = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True)
            return Image.fromarray(rgb)
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img.load()
    return img


def renderizar(path, lado):
    """Retorna bytes JPEG com o maior lado limitado a `lado`."""
    chave = (path, lado, os.path.getmtime(path))
    with _lock:
        if chave in _cache:
            _cache.move_to_end(chave)
            return _cache[chave]
    img = _abrir(path)
    img.thumbnail((lado, lado))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85 if lado > 400 else 75)
    dados = buf.getvalue()
    with _lock:
        _cache[chave] = dados
        while len(_cache) > _MAX_CACHE:
            _cache.popitem(last=False)
    return dados
