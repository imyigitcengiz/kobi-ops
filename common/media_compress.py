"""
Sunucuda yüklenen medya dosyalarını türüne göre sıkıştırır.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile

from common.media_files import classify_media_kind, file_extension

logger = logging.getLogger(__name__)


def _compress_enabled() -> bool:
    return getattr(settings, 'MEDIA_COMPRESS_ENABLED', True)


def _image_max_side() -> int:
    return int(getattr(settings, 'MEDIA_IMAGE_MAX_SIDE', 1920))


def _image_quality() -> int:
    return int(getattr(settings, 'MEDIA_IMAGE_MAX_QUALITY', 85))


def _ffmpeg_path() -> str:
    return getattr(settings, 'MEDIA_FFMPEG_PATH', 'ffmpeg') or 'ffmpeg'


def _safe_stem(name: str) -> str:
    stem = Path(name).stem or 'dosya'
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in stem)[:80]


def _wrap_bytes(
    data: bytes,
    *,
    name: str,
    content_type: str,
    original: UploadedFile,
) -> InMemoryUploadedFile:
    return InMemoryUploadedFile(
        file=BytesIO(data),
        field_name=getattr(original, 'field_name', None),
        name=name,
        content_type=content_type,
        size=len(data),
        charset=None,
    )


def _compress_image(uploaded: UploadedFile) -> tuple[UploadedFile | None, dict]:
    from PIL import Image, ImageOps

    original_size = uploaded.size
    uploaded.seek(0)
    img = Image.open(uploaded)
    img = ImageOps.exif_transpose(img)

    ext = file_extension(uploaded.name)
    if ext == '.svg' or getattr(img, 'is_animated', False):
        uploaded.seek(0)
        return None, {'skipped': 'svg_or_animated'}

    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode in ('RGBA', 'LA'):
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    max_side = _image_max_side()
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    out_format = getattr(settings, 'MEDIA_IMAGE_FORMAT', 'JPEG').upper()
    if out_format not in ('JPEG', 'WEBP'):
        out_format = 'JPEG'

    buf = BytesIO()
    save_kwargs = {'optimize': True, 'quality': _image_quality()}
    if out_format == 'JPEG':
        save_kwargs['progressive'] = True
        content_type = 'image/jpeg'
        out_name = f'{_safe_stem(uploaded.name)}.jpg'
    else:
        content_type = 'image/webp'
        out_name = f'{_safe_stem(uploaded.name)}.webp'

    img.save(buf, format=out_format, **save_kwargs)
    data = buf.getvalue()
    if len(data) >= original_size * 0.98:
        uploaded.seek(0)
        return None, {'skipped': 'no_gain'}

    processed = _wrap_bytes(data, name=out_name, content_type=content_type, original=uploaded)
    return processed, {
        'method': f'image_{out_format.lower()}',
        'original_bytes': original_size,
        'stored_bytes': len(data),
    }


def _ffmpeg_available() -> bool:
    try:
        result = subprocess.run(
            [_ffmpeg_path(), '-version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=8,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _compress_with_ffmpeg(
    uploaded: UploadedFile,
    *,
    kind: str,
) -> tuple[UploadedFile | None, dict]:
    if not _ffmpeg_available():
        return None, {'skipped': 'ffmpeg_missing'}

    original_size = uploaded.size
    suffix = file_extension(uploaded.name) or '.bin'
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4' if kind == 'video' else '.m4a')
    try:
        uploaded.seek(0)
        for chunk in uploaded.chunks():
            tmp_in.write(chunk)
        tmp_in.flush()
        tmp_in.close()

        if kind == 'video':
            cmd = [
                _ffmpeg_path(), '-y', '-i', tmp_in.name,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '28',
                '-movflags', '+faststart',
                '-c:a', 'aac', '-b:a', '128k',
                tmp_out.name,
            ]
            content_type = 'video/mp4'
            out_name = f'{_safe_stem(uploaded.name)}.mp4'
        else:
            cmd = [
                _ffmpeg_path(), '-y', '-i', tmp_in.name,
                '-vn', '-c:a', 'aac', '-b:a', '128k',
                tmp_out.name,
            ]
            content_type = 'audio/mp4'
            out_name = f'{_safe_stem(uploaded.name)}.m4a'

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(getattr(settings, 'MEDIA_FFMPEG_TIMEOUT', 300)),
            check=False,
        )
        if result.returncode != 0 or not os.path.exists(tmp_out.name) or os.path.getsize(tmp_out.name) == 0:
            logger.warning('ffmpeg sıkıştırma başarısız: %s', result.stderr[-500:] if result.stderr else '')
            return None, {'skipped': 'ffmpeg_failed'}

        with open(tmp_out.name, 'rb') as handle:
            data = handle.read()

        if len(data) >= original_size * 0.98:
            return None, {'skipped': 'no_gain'}

        processed = _wrap_bytes(data, name=out_name, content_type=content_type, original=uploaded)
        return processed, {
            'method': f'{kind}_ffmpeg',
            'original_bytes': original_size,
            'stored_bytes': len(data),
        }
    finally:
        for path in (tmp_in.name, tmp_out.name):
            if path and os.path.exists(path):
                os.unlink(path)


def prepare_media_file_for_storage(uploaded: UploadedFile) -> tuple[UploadedFile, dict]:
    """
    Yüklenen dosyayı diske yazmadan önce işler.
    Dönüş: (işlenmiş dosya, sıkıştırma özeti)
    """
    original_size = getattr(uploaded, 'size', 0) or 0
    base_meta = {
        'kind': classify_media_kind(uploaded.name),
        'original_bytes': original_size,
        'stored_bytes': original_size,
        'method': 'none',
        'compressed': False,
    }

    if not _compress_enabled() or not uploaded:
        uploaded.seek(0)
        return uploaded, base_meta

    kind = base_meta['kind']
    processed = None
    detail: dict = {}

    try:
        if kind == 'image':
            processed, detail = _compress_image(uploaded)
        elif kind == 'video':
            processed, detail = _compress_with_ffmpeg(uploaded, kind='video')
        elif kind == 'audio':
            processed, detail = _compress_with_ffmpeg(uploaded, kind='audio')
    except Exception as exc:
        logger.exception('Medya sıkıştırma hatası (%s): %s', uploaded.name, exc)
        uploaded.seek(0)
        return uploaded, {**base_meta, 'error': str(exc)}

    if processed is None:
        uploaded.seek(0)
        return uploaded, {**base_meta, **detail, 'compressed': False}

    stored = getattr(processed, 'size', 0) or detail.get('stored_bytes', 0)
    saved_pct = 0
    if original_size > 0:
        saved_pct = round(100 - (stored / original_size * 100), 1)

    processed._gy_compressed = True  # noqa: SLF001
    return processed, {
        'kind': kind,
        'original_bytes': original_size,
        'stored_bytes': stored,
        'method': detail.get('method', kind),
        'compressed': True,
        'saved_percent': saved_pct,
        **{k: v for k, v in detail.items() if k not in base_meta},
    }


def compress_model_file_field(instance, field_name: str, *, model=None) -> None:
    """Model kaydı öncesi FileField/ImageField dosyasını sıkıştırır."""
    uploaded = getattr(instance, field_name, None)
    if not uploaded:
        return
    if getattr(uploaded, '_gy_compressed', False):
        return

    if instance.pk and model is not None:
        try:
            old = model.objects.only(field_name).get(pk=instance.pk)
            old_file = getattr(old, field_name, None)
            if old_file and old_file.name == uploaded.name:
                return
        except model.DoesNotExist:
            pass

    processed, _meta = prepare_media_file_for_storage(uploaded)
    setattr(instance, field_name, processed)
