# -*- coding: utf-8 -*-
"""
Resolver para hls.astr.digital
Aceita URLs diretas com .m3u8 (stream adaptativo HLS)
Compatível com ResolveURL (Kodi)
"""

from resolveurl import common
from resolveurl.lib import helpers
from resolveurl.resolver import ResolveUrl, ResolverError
import re

class HLSAstrDigitalResolver(ResolveUrl):
    name = 'hls.astr.digital'
    domains = ['hls.astr.digital']

    # Reconhece URLs tipo:
    # https://hls.astr.digital/hls/.../master.m3u8?hash=...&expires=...
    pattern = r'(?://|\.)(hls(?:\d+)?\.astr\.digital)/(hls/[A-Za-z0-9/_\-\.\?\=\&]+\.m3u8[^\s\'"]*)'

    def get_url(self, host, media_id):
        """Constrói a URL de streaming final"""
        host = host.strip()
        media_id = media_id.strip()
        built_url = f"https://{host}/{media_id}"
        print(f"[HLSAstrDigital] URL construída: {built_url}")
        return built_url

    def get_media_url(self, host, media_id):
        print(f"[HLSAstrDigital] Iniciando resolução de HLS...")
        hls_url = self.get_url(host, media_id)

        # Valida se a URL contém .m3u8
        if ".m3u8" not in hls_url:
            raise ResolverError(f"Esta URL parece inválida (não contém .m3u8): {hls_url}")

        # Cabeçalhos — evita 403 Forbidden
        headers = {'User-Agent': common.RAND_UA}
        resolved = hls_url + helpers.append_headers(headers)
        print(f"[HLSAstrDigital] Link HLS resolvido: {resolved}")
        return resolved