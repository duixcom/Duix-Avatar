"""Bounded reference downloads with per-hop address checks and pinned sockets."""
import http.client
import ipaddress
import logging
import os
from pathlib import Path
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

logger = logging.getLogger(__name__)


class ReferenceDownloadError(ValueError):
    pass


class ReferenceDownloader:
    def __init__(self, allowed_networks=(), max_bytes=None,
                 timeout=30.0, max_redirects=3):
        self.allowed_networks = tuple(ipaddress.ip_network(value, strict=False)
                                      for value in allowed_networks)
        if max_bytes is None:
            max_bytes = int(os.environ.get('DUIX_REFERENCE_URL_MAX_BYTES', str(50 * 1024 * 1024)))
        if not isinstance(max_bytes, int) or max_bytes < 200:
            raise ValueError('DUIX_REFERENCE_URL_MAX_BYTES must be an integer of at least 200 bytes')
        self.max_bytes, self.timeout, self.max_redirects = max_bytes, timeout, max_redirects

    def _permitted(self, address):
        ip = ipaddress.ip_address(address)
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if ip.is_unspecified or ip.is_multicast:
            return False
        if any(ip.version == network.version and ip in network for network in self.allowed_networks):
            return True
        return ip.is_global and not ip.is_reserved

    def _target(self, url):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ReferenceDownloadError('Reference URL must use HTTP or HTTPS')
        if parsed.username is not None or parsed.password is not None:
            raise ReferenceDownloadError('Reference URL must not contain embedded credentials')
        host = parsed.hostname.encode('idna').decode('ascii')
        if '%' in host or any(ord(char) < 33 for char in url):
            raise ReferenceDownloadError('Reference URL contains invalid characters')
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = []
        for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            address = item[4][0]
            if address not in addresses:
                addresses.append(address)
        if not addresses or any(not self._permitted(ip) for ip in addresses):
            raise ReferenceDownloadError('Reference URL resolves to a restricted address')
        return parsed, host, port, addresses

    def download(self, url, destination):
        """Fetch into caller-owned session; errors never include URL secrets.

        Each TCP connection uses an already-checked address, avoiding a second
        DNS resolution between policy validation and connection. HTTPS retains
        the original host for certificate validation and SNI. Environment
        proxies are intentionally unused.
        """
        destination = Path(destination)
        deadline = time.monotonic() + self.timeout
        connection = None
        response = None
        created = False
        phase = 'address resolution'
        received = 0
        selected_ip = None
        try:
            for hop in range(self.max_redirects + 1):
                parsed, host, port, addresses = self._target(url)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ReferenceDownloadError('Reference audio download timed out')
                if parsed.scheme == 'https':
                    connection = http.client.HTTPSConnection(host, port, timeout=remaining,
                                                             context=ssl.create_default_context())
                else:
                    connection = http.client.HTTPConnection(host, port, timeout=remaining)

                def connect_checked(address, timeout=None, source_address=None):
                    nonlocal selected_ip
                    # Do not resolve the hostname again. Try only checked IPs.
                    for ip in addresses:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            selected_ip = ip
                            transport = socket.create_connection((ip, port), timeout=min(10, remaining),
                                                                 source_address=source_address)
                            transport.settimeout(max(0.001, deadline - time.monotonic()))
                            return transport
                        except OSError:
                            continue
                    raise ReferenceDownloadError('Cannot connect to reference audio server')

                connection._create_connection = connect_checked
                path = parsed.path or '/'
                if parsed.query:
                    path += '?' + parsed.query
                phase = 'connection'
                connection.request('GET', path, headers={'User-Agent': 'Duix-GB10-Reference/1.0',
                                                         'Accept': '*/*', 'Connection': 'close'})
                phase = 'response headers'
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    response.close(); response = None
                    connection.close(); connection = None
                    if not location or hop == self.max_redirects:
                        raise ReferenceDownloadError('Reference audio redirect limit exceeded or missing target')
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ReferenceDownloadError('Reference audio server returned HTTP %d' % response.status)
                declared = response.getheader('Content-Length')
                if declared is not None and (not declared.isdecimal() or int(declared) > self.max_bytes):
                    raise ReferenceDownloadError('Reference audio exceeds download size limit or has invalid length')
                received = 0
                phase = 'response body'
                with destination.open('xb') as output:
                    created = True
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ReferenceDownloadError('Reference audio download timed out')
                        transport = connection.sock or getattr(getattr(response.fp, 'raw', None), '_sock', None)
                        if transport is not None:
                            transport.settimeout(remaining)
                        block = response.read1(min(65536, self.max_bytes - received + 1))
                        if not block:
                            break
                        received += len(block)
                        if received > self.max_bytes:
                            raise ReferenceDownloadError('Reference audio exceeds download size limit')
                        output.write(block)
                if received < 200:
                    raise ReferenceDownloadError('Reference audio download is empty or too short')
                if declared is not None and received != int(declared):
                    raise ReferenceDownloadError('Reference audio download was incomplete')
                return destination
            raise ReferenceDownloadError('Reference audio redirect limit exceeded')
        except Exception as exc:
            if created:
                destination.unlink(missing_ok=True)
            if isinstance(exc, ReferenceDownloadError):
                raise
            logger.warning('Reference download failure: phase=%s received_bytes=%d peer=%s error=%s',
                           phase, received, selected_ip, type(exc).__name__)
            # urllib/http.client/socket errors may echo signed query strings or
            # user-info. Expose only a fixed message and exception class.
            raise ReferenceDownloadError('Reference audio download failed during %s (%s)' % (phase, type(exc).__name__)) from None
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()


def resolve_reference(root, value, session, downloader, resolve_local):
    if value.lower().startswith(('http://', 'https://')):
        return downloader.download(value, Path(session) / 'reference-audio.bin')
    return resolve_local(root, value)
