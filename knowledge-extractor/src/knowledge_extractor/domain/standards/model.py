"""Hand-curated protocol standards tables.

This dataset has no external source to download — the tables below are the
authoritative copy. Edit in place to extend coverage. The downloader is a
no-op that always reports ready; the extractor walks these tables.
"""

from __future__ import annotations

from ...base import DatasetMeta, RawLayout


META = DatasetMeta(
    name="standards",
    category="domain",
    version="2026-04",
    license="public domain (hand-curated)",
    url="https://www.iana.org/",
    layer_band="knowledge",
    description="Protocol standards: HTTP, DNS, ports, MIME types, TLS",
)


class StandardsRawLayout(RawLayout):
    """Standards has no raw artifacts — layout is a marker only."""

    def verify(self) -> bool:
        return True


HTTP_STATUS: dict[str, str] = {
    "100": "continue",
    "101": "switching protocols",
    "200": "ok",
    "201": "created",
    "202": "accepted",
    "204": "no content",
    "206": "partial content",
    "301": "moved permanently",
    "302": "found",
    "303": "see other",
    "304": "not modified",
    "307": "temporary redirect",
    "308": "permanent redirect",
    "400": "bad request",
    "401": "unauthorized",
    "403": "forbidden",
    "404": "not found",
    "405": "method not allowed",
    "406": "not acceptable",
    "408": "request timeout",
    "409": "conflict",
    "410": "gone",
    "413": "payload too large",
    "414": "uri too long",
    "415": "unsupported media type",
    "418": "teapot",
    "422": "unprocessable entity",
    "425": "too early",
    "426": "upgrade required",
    "428": "precondition required",
    "429": "too many requests",
    "431": "request header fields too large",
    "451": "unavailable for legal reasons",
    "500": "internal server error",
    "501": "not implemented",
    "502": "bad gateway",
    "503": "service unavailable",
    "504": "gateway timeout",
    "505": "http version not supported",
    "507": "insufficient storage",
    "511": "network authentication required",
}

HTTP_METHODS: dict[str, str] = {
    "get": "retrieve a resource",
    "head": "retrieve headers only",
    "post": "submit data to a resource",
    "put": "replace a resource",
    "patch": "partially update a resource",
    "delete": "remove a resource",
    "options": "describe allowed methods",
    "trace": "echo the request",
    "connect": "establish a tunnel",
}

DNS_RECORDS: dict[str, str] = {
    "a": "ipv4 address",
    "aaaa": "ipv6 address",
    "cname": "canonical name alias",
    "mx": "mail exchange",
    "ns": "name server",
    "ptr": "reverse pointer",
    "soa": "start of authority",
    "srv": "service locator",
    "txt": "text record",
    "caa": "certificate authority authorization",
    "dnskey": "dnssec public key",
    "ds": "delegation signer",
    "rrsig": "dnssec signature",
    "tlsa": "tls association",
    "naptr": "naming authority pointer",
    "spf": "sender policy framework",
}

TCP_PORTS: dict[str, str] = {
    "20": "ftp data",
    "21": "ftp control",
    "22": "ssh",
    "23": "telnet",
    "25": "smtp",
    "53": "dns",
    "80": "http",
    "110": "pop3",
    "143": "imap",
    "443": "https",
    "465": "smtps",
    "587": "smtp submission",
    "993": "imaps",
    "995": "pop3s",
    "3306": "mysql",
    "5432": "postgresql",
    "6379": "redis",
    "8080": "http alternate",
    "8443": "https alternate",
    "27017": "mongodb",
}

UDP_PORTS: dict[str, str] = {
    "53": "dns",
    "67": "dhcp server",
    "68": "dhcp client",
    "69": "tftp",
    "123": "ntp",
    "161": "snmp",
    "500": "isakmp",
    "514": "syslog",
    "1194": "openvpn",
    "51820": "wireguard",
}

MIME_TYPES: dict[str, str] = {
    "text/plain": "txt",
    "text/html": "html",
    "text/css": "css",
    "text/csv": "csv",
    "text/markdown": "md",
    "application/json": "json",
    "application/xml": "xml",
    "application/yaml": "yaml",
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/octet-stream": "bin",
    "application/javascript": "js",
    "application/wasm": "wasm",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/webp": "webp",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "font/woff": "woff",
    "font/woff2": "woff2",
}

TLS_VERSIONS: dict[str, str] = {
    "ssl 2.0": "deprecated",
    "ssl 3.0": "deprecated",
    "tls 1.0": "deprecated",
    "tls 1.1": "deprecated",
    "tls 1.2": "supported",
    "tls 1.3": "current",
}


TABLES: list[tuple[str, dict[str, str]]] = [
    ("http_status", HTTP_STATUS),
    ("http_method", HTTP_METHODS),
    ("dns_record",  DNS_RECORDS),
    ("tcp_port",    TCP_PORTS),
    ("udp_port",    UDP_PORTS),
    ("mime_type",   MIME_TYPES),
    ("tls_version", TLS_VERSIONS),
]
