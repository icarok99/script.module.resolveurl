# -*- coding: utf-8 -*-

from resolveurl.lib import helpers
from resolveurl.plugins.__resolve_generic__ import ResolveGeneric
from resolveurl import common  # <-- Adicionado para acessar RAND_UA
from urllib.parse import urljoin

class DoramasOnlineResolver(ResolveGeneric):
    name = "DoramasOnline"
    domains = ["doramasonline.org"]
    pattern = r'(?://|\.)(doramasonline\.org)/cdn9/odacdn/v2/\?id=([^&]+)'

    def get_media_url(self, host, media_id):
        embed_url = f'https://doramasonline.org/cdn9/odacdn/v2/?id={media_id}'
        
        print(f"DoramasOnline: Acessando embed → {embed_url}")

        stream_url = helpers.get_media_url(
            embed_url,
            patterns=[
                r'''sources:\s*\[\s*\{\s*["\']file["\']\s*:\s*["\'](?P<url>[^"\']+\.m3u8[^"\']*)["\']''',
                r'''["\']file["\']\s*:\s*["\'](?P<url>[^"\']+)["\']''',
                r'''file:\s*["\'](?P<url>[^"']+)["\']'''
            ],
            generic_patterns=False,
            referer='https://doramasonline.org/'
        )

        # === Parsing da master playlist para pegar a melhor qualidade ===
        if stream_url.lower().endswith('.m3u8'):
            print("DoramasOnline: HLS detectado. Parseando master playlist para maior qualidade.")
            playlist_headers = {
                'User-Agent': common.RAND_UA,        # <-- Corrigido
                'Referer': 'https://doramasonline.org/',
                'Origin': 'https://doramasonline.org'
            }
            try:
                playlist_content = self.net.http_GET(stream_url, headers=playlist_headers).content.decode('utf-8')
                
                variant_lines = [line.strip() for line in playlist_content.splitlines()
                                 if line.strip() and not line.startswith('#')]
                
                if variant_lines:
                    highest_variant = variant_lines[-1]
                    stream_url = highest_variant if highest_variant.startswith('http') else urljoin(stream_url, highest_variant)
                    print(f"DoramasOnline: Melhor variante selecionada → {stream_url}")
                else:
                    print("DoramasOnline: Nenhuma variante encontrada, usando master playlist.")
            except Exception as e:
                print(f"DoramasOnline: Erro ao parsear playlist HLS: {e}")

        # Headers finais obrigatórios
        final_url = stream_url + helpers.append_headers({
            'User-Agent': common.RAND_UA,            # <-- Corrigido
            'Referer': 'https://doramasonline.org/',
            'Origin': 'https://doramasonline.org'
        })

        print("DoramasOnline: URL final → " + final_url)
        return final_url

    def get_url(self, host, media_id):
        return f'https://doramasonline.org/cdn9/odacdn/v2/?id={media_id}'