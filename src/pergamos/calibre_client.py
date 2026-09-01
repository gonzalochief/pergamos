"""Small stdlib-only client for the Calibre Content Server OPDS interface."""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .config import Settings

OPDS_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/terms/"
CALIBRE_NS = "http://calibre.kovidgoyal.net/2009/metadata"
NS = {"atom": OPDS_NS, "dc": DC_NS, "calibre": CALIBRE_NS}


class CalibreError(RuntimeError):
    """Raised when the Content Server cannot satisfy a request."""


@dataclass
class Book:
    identifier: str
    title: str
    authors: list[str] = field(default_factory=list)
    summary: str | None = None
    publisher: str | None = None
    published: str | None = None
    language: str | None = None
    tags: list[str] = field(default_factory=list)
    formats: list[dict[str, str]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary,
            "publisher": self.publisher,
            "published": self.published,
            "language": self.language,
            "tags": self.tags,
            "formats": self.formats,
            "links": self.links,
        }


@dataclass
class FeedPage:
    books: list[Book]
    next_url: str | None = None


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _local_identifier(value: str) -> str:
    return value.rsplit("/", 1)[-1].strip() or value


def _application_id(links: list[dict[str, str]]) -> str | None:
    for link in links:
        match = re.search(r"/get/[^/]+/([^/?]+)/", link["url"])
        if match:
            return match.group(1)
    return None


def parse_feed(xml: bytes, base_url: str) -> FeedPage:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise CalibreError("Calibre returned malformed OPDS XML") from error

    books: list[Book] = []
    for entry in root.findall("atom:entry", NS):
        identifier = _text(entry.find("dc:identifier", NS)) or _text(entry.find("atom:id", NS))
        title = _text(entry.find("atom:title", NS))
        if not identifier or not title:
            continue

        links: list[dict[str, str]] = []
        formats: list[dict[str, str]] = []
        for link in entry.findall("atom:link", NS):
            href = link.get("href")
            if not href:
                continue
            link_data = {"url": urllib.parse.urljoin(base_url, href)}
            for key in ("rel", "type", "title", "length"):
                if link.get(key):
                    link_data[key] = link.get(key, "")
            links.append(link_data)
            if link.get("rel") == "http://opds-spec.org/acquisition" or link.get("type"):
                formats.append(link_data)

        authors = [_text(author.find("atom:name", NS)) for author in entry.findall("atom:author", NS)]
        application_id = _application_id(links)
        books.append(
            Book(
            identifier=application_id or _local_identifier(identifier),
                title=title,
                authors=[author for author in authors if author],
                summary=_text(entry.find("atom:summary", NS)) or _text(entry.find("atom:content", NS)),
                publisher=_text(entry.find("dc:publisher", NS)),
                published=_text(entry.find("dc:date", NS)),
                language=_text(entry.find("dc:language", NS)),
                tags=[tag.text.strip() for tag in entry.findall("atom:category", NS) if tag.text],
                formats=formats,
                links=links,
            )
        )

    next_link = root.find("atom:link[@rel='next']", NS)
    next_url = urllib.parse.urljoin(base_url, next_link.get("href")) if next_link is not None and next_link.get("href") else None
    return FeedPage(books=books, next_url=next_url)


class CalibreClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _request(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"Accept": "application/atom+xml, application/xml"})
        if self.settings.username and self.settings.password:
            token = base64.b64encode(f"{self.settings.username}:{self.settings.password}".encode()).decode()
            request.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise CalibreError("Calibre authentication failed; check CALIBRE_USERNAME and CALIBRE_PASSWORD") from error
            raise CalibreError(f"Calibre returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise CalibreError(f"Could not connect to Calibre at {self.settings.calibre_url}: {error.reason if isinstance(error, urllib.error.URLError) else error}") from error

    def feed(self, path_or_url: str) -> FeedPage:
        url = path_or_url if path_or_url.startswith(("http://", "https://")) else f"{self.settings.calibre_url}/{path_or_url.lstrip('/')}"
        return parse_feed(self._request(url), url)

    def list_libraries(self) -> FeedPage:
        return self.feed("opds")

    def search(self, query: str, limit: int = 20, offset: int = 0) -> list[Book]:
        params = urllib.parse.urlencode({"offset": offset})
        next_path = f"opds/search/{urllib.parse.quote(query, safe='')}?{params}"
        books: list[Book] = []
        seen_urls: set[str] = set()

        while next_path and len(books) < limit:
            page = self.feed(next_path)
            books.extend(page.books)
            if not page.next_url or page.next_url in seen_urls:
                break
            seen_urls.add(page.next_url)
            next_path = page.next_url

        return books[:limit]

    def get_book(self, identifier: str) -> Book:
        url = f"{self.settings.calibre_url}/ajax/book/{urllib.parse.quote(identifier, safe='')}"
        try:
            data = json.loads(self._request(url))
        except json.JSONDecodeError as error:
            raise CalibreError("Calibre returned malformed book metadata JSON") from error
        if not isinstance(data, dict) or not data.get("title"):
            raise CalibreError(f"Book '{identifier}' was not found")

        formats = []
        for format_name, format_url in data.get("main_format", {}).items():
            formats.append({
                "format": format_name,
                "url": urllib.parse.urljoin(self.settings.calibre_url, format_url),
            })
        for format_name, format_url in data.get("other_formats", {}).items():
            formats.append({
                "format": format_name,
                "url": urllib.parse.urljoin(self.settings.calibre_url, format_url),
            })
        return Book(
            identifier=str(data.get("application_id", identifier)),
            title=str(data["title"]),
            authors=[str(author) for author in data.get("authors", [])],
            summary=data.get("comments"),
            publisher=data.get("publisher"),
            published=data.get("pubdate"),
            language=", ".join(str(language) for language in data.get("languages", [])) or None,
            tags=[str(tag) for tag in data.get("tags", [])],
            formats=formats,
        )