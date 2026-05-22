"""Medya dosya türleri — yükleme, sınıflandırma ve HTML accept."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico',
    '.heic', '.heif', '.tif', '.tiff',
}
VIDEO_EXTENSIONS = {
    '.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v', '.mpeg', '.mpg', '.wmv', '.3gp',
}
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma',
}
DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.rtf', '.odt', '.ods', '.odp', '.odg',
    '.pages', '.numbers', '.key',
}
ARCHIVE_EXTENSIONS = {
    '.zip', '.rar', '.7z', '.tar', '.gz',
}
CAD_EXTENSIONS = {'.dwg', '.dxf'}

ALLOWED_UPLOAD_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | VIDEO_EXTENSIONS
    | AUDIO_EXTENSIONS
    | DOCUMENT_EXTENSIONS
    | ARCHIVE_EXTENSIONS
    | CAD_EXTENSIONS
)

KIND_LABELS = {
    'image': 'Görsel',
    'video': 'Video',
    'audio': 'Ses',
    'document': 'Belge',
    'archive': 'Arşiv',
    'other': 'Diğer',
}


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def classify_media_kind(filename: str) -> str:
    ext = file_extension(filename)
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    if ext in AUDIO_EXTENSIONS:
        return 'audio'
    if ext in DOCUMENT_EXTENSIONS or ext in CAD_EXTENSIONS:
        return 'document'
    if ext in ARCHIVE_EXTENSIONS:
        return 'archive'
    return 'other'


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, 'Dosya')


def is_allowed_upload(filename: str) -> bool:
    ext = file_extension(filename)
    if ext in ALLOWED_UPLOAD_EXTENSIONS:
        return True
    # Bilinmeyen uzantı — yine de yüklenebilir (CAD, özel formatlar)
    return bool(ext) and ext not in {'.exe', '.bat', '.cmd', '.msi', '.dll', '.sh', '.ps1', '.js', '.html', '.htm'}


def html_accept_attribute() -> str:
    """Tarayıcı dosya seçici için accept listesi."""
    mime_groups = 'image/*,video/*,audio/*'
    extensions = ','.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
    return f'{mime_groups},{extensions}'


def upload_hint_text() -> str:
    return (
        'Resim, video, ses, PDF, Word, Excel, PowerPoint, ZIP ve diğer belgeler '
        '(çoklu seçim)'
    )
