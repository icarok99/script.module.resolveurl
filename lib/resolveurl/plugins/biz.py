# -*- coding: utf-8 -*-
"""
Resolver para assistir.biz com redirecionamento MediaFire
Compatível com ResolveURL (Kodi)
"""

from resolveurl.lib import helpers
from resolveurl import common
from resolveurl.resolver import ResolveUrl, ResolverError
import re

class AssistirBizResolver(ResolveUrl):
    name = 'assistir.biz'
    domains = ['assistir.biz']

    # Agora cobre tanto /direct/ quanto /playserie/
    pattern = r'(?://|\.)(assistir\.biz)/(?:direct|playserie)/([A-Za-z0-9/_\-\.\?=]+)'

    def get_url(self, host, media_id):
        """
        Constrói a URL completa de entrada.
        Detecta automaticamente se o identificador é de /direct/ ou /playserie/.
        """
        if '/' in media_id and re.match(r'^\d+/', media_id):
            # Detecção simples: IDs numéricos iniciais geralmente vêm de /playserie/
            built_url = f'https://{host}/playserie/{media_id}'
            print(f"[AssistirBizResolver] URL de 'playserie' construída: {built_url}")
        else:
            built_url = f'https://{host}/direct/{media_id}'
            print(f"[AssistirBizResolver] URL de 'direct' construída: {built_url}")

        return built_url

    def get_media_url(self, host, media_id):
        print(f"[AssistirBizResolver] Iniciando resolução de URL...")
        web_url = self.get_url(host, media_id)
        headers = {'User-Agent': common.RAND_UA}

        try:
            print(f"[AssistirBizResolver] Tentando obter redirecionamento direto via helpers.get_redirect_url...")
            redirect_url = helpers.get_redirect_url(web_url, headers)
            print(f"[AssistirBizResolver] Resultado do redirect: {redirect_url}")
        except Exception as e:
            print(f"[AssistirBizResolver] Erro ao tentar get_redirect_url: {e}")
            redirect_url = None

        if redirect_url and 'mediafire.com' in redirect_url:
            print(f"[AssistirBizResolver] Redirecionamento direto encontrado para MediaFire: {redirect_url}")
            return redirect_url

        print(f"[AssistirBizResolver] Redirecionamento direto não disponível. Tentando buscar no HTML...")

        try:
            response = self.net.http_GET(web_url, headers=headers, redirect=True)
            html = response.content

            if 'mediafire' in html.lower():
                print("[AssistirBizResolver] HTML contém referência a MediaFire (provável redirecionamento).")

            match = re.search(r'https://download\d+\.mediafire\.com/[^\s\'"]+\.mp4', html)
            if match:
                direct_url = match.group(0)
                print(f"[AssistirBizResolver] Link direto encontrado no HTML: {direct_url}")
                return direct_url
            else:
                print("[AssistirBizResolver] Nenhum link .mp4 encontrado no HTML.")

        except Exception as e:
            print(f"[AssistirBizResolver] Erro ao buscar HTML: {e}")
            raise ResolverError(f"Erro ao acessar {web_url}: {str(e)}")

        raise ResolverError(f"Nenhum link direto encontrado para {web_url}")