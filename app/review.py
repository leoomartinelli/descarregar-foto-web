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
_cache_original = OrderedDict()   # fotos em tamanho cheio para o zoom: grandes, entao poucas na memoria
_MAX_ORIGINAL = 3


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


def original(path):
    """(bytes, tipo) da foto no tamanho original, para o zoom da tela de selecao. JPEG e PNG vao como estao no
    disco (sem recompactar: qualidade maxima; o navegador aplica a rotacao do EXIF). RAW e revelado em tamanho cheio."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png"):
        with open(path, "rb") as f:
            return f.read(), "image/png" if ext == ".png" else "image/jpeg"
    chave = (path, os.path.getmtime(path))
    with _lock:
        if chave in _cache_original:
            _cache_original.move_to_end(chave)
            return _cache_original[chave], "image/jpeg"
    import rawpy
    with rawpy.imread(path) as raw:
        img = None
        try:
            thumb = raw.extract_thumb()        # a previa embutida costuma ter a resolucao cheia e sai na hora
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = ImageOps.exif_transpose(Image.open(io.BytesIO(thumb.data)))
                if max(img.size) < 3000:
                    img = None
        except Exception:
            img = None
        if img is None:
            img = Image.fromarray(raw.postprocess(use_camera_wb=True, no_auto_bright=True))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    with _lock:
        _cache_original[chave] = buf.getvalue()
        while len(_cache_original) > _MAX_ORIGINAL:
            _cache_original.popitem(last=False)
        return _cache_original[chave], "image/jpeg"


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
