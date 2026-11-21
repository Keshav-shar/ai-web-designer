"""netfix.py - keep the worker online through flaky DNS on this PC.

Symptom (worker console): `ConnectError: [Errno 11001] getaddrinfo failed` for the Supabase host, every few minutes,
while the same name resolves fine moments later. The network is up; only the name lookup fails. Every Supabase,
Gemini and Groq call then fails before it is sent.

install() wraps socket.getaddrinfo once per process:
  1. the normal system lookup; on success the answer is remembered per (host, port);
  2. if it fails, the last good answer for that host is reused (Supabase / Google / Groq sit behind stable anycast IPs);
  3. if there is none yet, the name is asked over DNS-over-HTTPS straight to 1.1.1.1 / 8.8.8.8 by IP (no DNS needed).
TLS is unaffected: the client still connects with the real hostname (SNI + certificate check); only the socket
address comes from the fallback. Nothing is written to disk and no system setting is changed.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import threading
import urllib.request

_DOH = ("https://1.1.1.1/dns-query?name={}&type=A", "https://8.8.8.8/resolve?name={}&type=A")
_cache: dict[tuple[str, object], list] = {}
_lock = threading.Lock()
_installed = False
_warned: set[str] = set()


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _doh(host: str) -> list[str]:
    ctx = ssl.create_default_context()
    for url in _DOH:
        try:
            req = urllib.request.Request(url.format(host), headers={"accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                ans = json.load(r).get("Answer") or []
            ips = [a["data"] for a in ans if a.get("type") == 1]
            if ips:
                return ips
        except Exception:  # noqa: BLE001 - try the next resolver
            continue
    return []


def install() -> None:
    global _installed
    if _installed:
        return
    real = socket.getaddrinfo

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002 - socket's own signature
        try:
            res = real(host, port, family, type, proto, flags)
        except socket.gaierror:
            if not isinstance(host, str) or not host or _is_ip(host) or host == "localhost":
                raise
            with _lock:
                cached = _cache.get((host, port))
            if cached:
                _note(host, "reusing its last good address")
                return cached
            ips = _doh(host)
            if not ips:
                raise
            _note(host, "resolved over DNS-over-HTTPS")
            res = [r for ip in ips for r in real(ip, port, socket.AF_INET, type, proto, flags)]
        else:
            if isinstance(host, str) and host and not _is_ip(host):
                with _lock:
                    _cache[(host, port)] = res
            return res
        with _lock:
            _cache[(host, port)] = res
        return res

    socket.getaddrinfo = getaddrinfo
    _installed = True


def _note(host: str, how: str) -> None:
    if host not in _warned:                       # once per host, so the console stays readable
        _warned.add(host)
        print(f"note: DNS lookup for {host} failed on this PC; {how} (netfix)", flush=True)
