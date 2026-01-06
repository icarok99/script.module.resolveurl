# -*- coding: utf-8 -*-
from resolveurl.lib import helpers
from resolveurl import common
from resolveurl.resolver import ResolveUrl, ResolverError
import re

try:
    from urllib.parse import urlparse, parse_qs, urljoin
except Exception:
    from urlparse import urlparse, parse_qs, urljoin


class NetcineResolver(ResolveUrl):
    name = 'netcine'
    domains = ['*']
    # regex genérico para futuros domínios
    pattern = r'(?://|\.)(n[a-z0-9-]*\.[a-z]{2,})/(.+)'

    def __init__(self):
        self.net = common.Net()

    def get_url(self, host, media_id):
        """
        Resolve várias formas de media_id para uma URL completa.
        Mantido para compatibilidade com usos antigos.
        """
        if media_id.startswith('http://') or media_id.startswith('https://'):
            return media_id
        if media_id.startswith('/'):
            return 'https://{0}{1}'.format(host, media_id)
        if '/' in media_id or '?' in media_id or '=' in media_id:
            return 'https://{0}/{1}'.format(host, media_id)
        return 'https://{host}/embed-{media_id}.html'.format(host=host, media_id=media_id)

    def get_media_url(self, host, media_id):
        web_url = self.get_url(host, media_id)
        print('[netcine] start get_media_url ->', web_url)
        if not web_url:
            raise ResolverError('URL inválida')

        headers = {'User-Agent': common.FF_USER_AGENT}
        try:
            p = urlparse(web_url)
            headers['Referer'] = '{0}://{1}/'.format(p.scheme, p.netloc)
            headers['Origin'] = '{0}://{1}'.format(p.scheme, p.netloc)
        except Exception:
            headers['Referer'] = web_url

        print('[netcine] headers (inicial) ->', headers)

        # 1) página inicial
        try:
            html = self.net.http_GET(web_url, headers=headers).content
            print('[netcine] página inicial obtida, tamanho:', len(html) if html else 0)
            print('[netcine] snippet:', (html[:200] + '...') if html and len(html) > 200 else html)
        except Exception:
            raise ResolverError('Falha ao obter a página')

        # 2) descobrir player_link
        player_link = None

        # prioridade: link dentro da .btn-container (Assistir Online / Download)
        m = re.search(r'<div[^>]*class=["\']btn-container["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if m:
            player_link = m.group(1)
            print('[netcine] player link encontrado na btn-container (raw):', player_link)
            if player_link.startswith('/'):
                try:
                    p = urlparse(web_url)
                    player_link = p.scheme + '://' + p.netloc + player_link
                    print('[netcine] player link absoluto:', player_link)
                except Exception:
                    pass

        # fallback genérico: procurar primeiro <a href> dentro de #content
        if not player_link:
            m2 = re.search(r'<div[^>]*id=["\']content["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
            if m2:
                player_link = m2.group(1)
                print('[netcine] player link encontrado no #content (raw):', player_link)
                if player_link.startswith('/'):
                    try:
                        p = urlparse(web_url)
                        player_link = p.scheme + '://' + p.netloc + player_link
                        print('[netcine] player link absoluto (content):', player_link)
                    except Exception:
                        pass

        # se ainda não achou, tenta achar qualquer <iframe src=> ou usa a própria web_url
        if not player_link:
            m3 = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m3:
                player_link = m3.group(1)
                print('[netcine] player link encontrado via iframe:', player_link)
                if player_link.startswith('/'):
                    try:
                        p = urlparse(web_url)
                        player_link = p.scheme + '://' + p.netloc + player_link
                    except Exception:
                        pass

        if not player_link:
            player_link = web_url
            print('[netcine] usando web_url como player_link fallback:', player_link)

        # 3) baixar player
        try:
            # atualiza Referer/Origin para o host do player (importante p/ CDN)
            try:
                pp = urlparse(player_link)
                headers['Referer'] = f"{pp.scheme}://{pp.netloc}/"
                headers['Origin'] = f"{pp.scheme}://{pp.netloc}"
            except Exception:
                pass

            player_html = self.net.http_GET(player_link, headers=headers).content
            print('[netcine] player HTML obtido, tamanho:', len(player_html) if player_html else 0)
            print('[netcine] player snippet:', (player_html[:200] + '...') if player_html and len(player_html) > 200 else player_html)
        except Exception:
            raise ResolverError('Falha ao obter o player')

        # 4) tentar encontrar as fontes
        # 4.1) base64 inline
        try:
            b64 = re.search(r'base64,([^"\']+)', player_html)
            if b64:
                decoded = helpers.b64decode(b64.group(1))
                srcs = helpers.scrape_sources(decoded)
                if srcs:
                    chosen = helpers.pick_source(helpers.sort_sources_list(srcs))
                    return self._finalize_headers(chosen, headers, player_link)
        except Exception:
            pass

        # 4.2) helpers.scrape_sources no HTML do player
        try:
            srcs = helpers.scrape_sources(player_html)
            print('[netcine] scrape_sources retornou:', srcs)
            if srcs:
                chosen = helpers.pick_source(helpers.sort_sources_list(srcs))
                print('[netcine] fonte escolhida (scrape_sources):', chosen)
                return self._finalize_headers(chosen, headers, player_link)
        except Exception:
            pass

        # 4.3) <source src=...>
        try:
            sources = re.findall(r'<source[^>]*\s+src=["\']([^"\']+)["\']', player_html, re.IGNORECASE)
            print('[netcine] <source> encontrados:', sources)
            if sources:
                src_list = [{'file': s} for s in sources]
                chosen = helpers.pick_source(helpers.sort_sources_list(src_list))
                print('[netcine] fonte escolhida (<source>):', chosen)
                return self._finalize_headers(chosen, headers, player_link)
        except Exception:
            pass

        # 4.4) JS players file: "..." ou file: '...'
        try:
            js_files = re.findall(r'file\s*:\s*["\']([^"\']+)["\']', player_html, re.IGNORECASE)
            print('[netcine] arquivos JS (file: ...):', js_files)
            if js_files:
                last_file = js_files[-1]
                print('[netcine] retornando última entrada JS file:', last_file)
                return self._finalize_headers(last_file, headers, player_link)
        except Exception:
            pass

        # 4.5) Lógica específica para NetCine HLS fallback (extração de n/p e construção do m3u8 proxy)
        try:
            parsed_player = urlparse(player_link)
            query_params = parse_qs(parsed_player.query)
            n = query_params.get('n', [''])[0]
            p = query_params.get('p', [''])[0]
            if n and p:
                fallback_path = '/media-player/dist/playerhls-fallback.php'
                fallback_query = f'?n={n}&p={p}'
                fallback_url = f"{parsed_player.scheme}://{parsed_player.netloc}{fallback_path}{fallback_query}"
                print('[netcine] fallback m3u8 construído:', fallback_url)
                
                # Fetch the fallback content
                try:
                    fallback_content = self.net.http_GET(fallback_url, headers=headers).content
                    print('[netcine] fallback content obtido, tamanho:', len(fallback_content) if fallback_content else 0)
                    print('[netcine] fallback snippet:', (fallback_content[:200] + '...') if fallback_content and len(fallback_content) > 200 else fallback_content)
                except Exception:
                    fallback_content = ''

                # Extract MP4 URL from the content (assuming it's in M3U8 or HTML)
                mp4_matches = re.findall(r'(https?://[^\s"\']+?\.mp4(?:\?[^\s"\']+)?)', fallback_content, re.IGNORECASE)
                if mp4_matches:
                    chosen = mp4_matches[-1]  # Take the last one, assuming it's the main segment
                    print('[netcine] MP4 extraído do fallback:', chosen)
                    return chosen  # no headers for fallback MP4
                
                # If it's a valid M3U8, return the fallback_url itself
                try:
                    if isinstance(fallback_content, bytes):
                        starts = fallback_content.decode('utf-8', errors='ignore').lstrip()
                    else:
                        starts = str(fallback_content).lstrip()
                    if starts.startswith('#EXTM3U'):
                        print('[netcine] retornando fallback M3U8 diretamente')
                        return self._finalize_headers(fallback_url, headers, player_link)
                except Exception:
                    pass
        except Exception as e:
            print('[netcine] erro na extração fallback:', str(e))

        print('[netcine] Video Link Not Found')
        raise ResolverError('Video Link Not Found')

    # ================== helpers ==================
    def _cookiejar(self):
        """Obtém o cookie jar interno do wrapper common.Net(), independente do atributo usado."""
        cj = None
        try:
            if hasattr(self.net, 'cookies') and self.net.cookies:
                cj = self.net.cookies
            elif hasattr(self.net, '_cj') and self.net._cj:
                cj = self.net._cj
            elif hasattr(self.net, 'cookiejar') and self.net.cookiejar:
                cj = self.net.cookiejar
            elif hasattr(self.net, 'session') and hasattr(self.net.session, 'cookies'):
                cj = self.net.session.cookies
        except Exception:
            cj = None
        return cj

    def _cookie_header_for(self, url):
        """Monta o header Cookie com base no cookie jar para o host do URL informado."""
        try:
            p = urlparse(url)
            host = p.netloc.lower()
        except Exception:
            return None

        jar = self._cookiejar()
        if not jar:
            return None

        def _match(domain, host):
            if not domain:
                return False
            d = domain.lstrip('.').lower()
            h = host.lower()
            return h == d or h.endswith('.' + d)

        pairs = []
        try:
            for c in jar:
                # ignora cookies vazios ou expirados (quando info existir)
                if not getattr(c, 'name', None) or getattr(c, 'value', None) in (None, ''):
                    continue
                cdomain = getattr(c, 'domain', '') or host
                if _match(cdomain, host):
                    pairs.append('%s=%s' % (c.name, c.value))
        except Exception:
            pass

        cookie_header = '; '.join(pairs) if pairs else None
        print('[netcine] cookie header para', host, '->', cookie_header)
        return cookie_header

    def _finalize_headers(self, chosen, headers, player_link):
        """ Ajusta Referer/Origin para o **player** e injeta Cookie real do jar para a **URL do vídeo**. """
        try:
            # Referer/Origin: usar o host do player (não o da mídia) — prática comum de CDN
            pp = urlparse(player_link)
            headers['Referer'] = f"{pp.scheme}://{pp.netloc}/"
            headers['Origin']  = f"{pp.scheme}://{pp.netloc}"
        except Exception:
            pass

        # Cookie: pegar cookies válidos para o host do vídeo; se não houver, tentar os do player
        ck = self._cookie_header_for(chosen)
        if not ck:
            ck = self._cookie_header_for(player_link)
        if ck:
            headers['Cookie'] = ck
        elif 'Cookie' in headers:
            # garante que não fique cookie falso antigo
            headers.pop('Cookie', None)

        print('[netcine] headers (final) ->', headers)
        return chosen + helpers.append_headers(headers)
