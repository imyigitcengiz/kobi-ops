from django import template

from common.media_files import html_accept_attribute, upload_hint_text

register = template.Library()


@register.simple_tag
def media_upload_accept():
    return html_accept_attribute()


@register.simple_tag
def media_upload_hint():
    return upload_hint_text()
