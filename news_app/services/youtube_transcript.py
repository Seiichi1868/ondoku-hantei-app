"""YouTube InnerTube 経由の字幕取得（Cloudflare Worker が 429 のときのサーバー側フォールバック）。"""

from __future__ import annotations

import json
import logging
import re
import ssl
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from news_app.config import DATA_DIR
from news_app.services.youtube import extract_video_id

logger = logging.getLogger(__name__)

INNERTUBE_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
DEFAULT_LANGUAGES = ("en", "ja")
CACHE_DIR = DATA_DIR / "youtube_transcripts"

INNERTUBE_CLIENTS = (
    {
        "name": "ANDROID",
        "context": {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}},
        "user_agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 14)",
    },
    {
        "name": "IOS",
        "context": {
            "client": {
                "clientName": "IOS",
                "clientVersion": "20.10.4",
                "deviceModel": "iPhone16,2",
            }
        },
        "user_agent": "com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)",
    },
)

_P_TAG_RE = re.compile(r'<p\s+t="(\d+)"\s+d="(\d+)"[^>]*>([\s\S]*?)</p>')
_S_TAG_RE = re.compile(r"<s[^>]*>([^<]*)</s>")
_TEXT_TAG_RE = re.compile(r'<text start="([^"]*)" dur="([^"]*)">([^<]*)</text>')
_TAG_RE = re.compile(r"<[^>]+>")


class TranscriptRateLimited(Exception):
    """YouTube がこの IP からの字幕リクエストを制限している。"""


class TranscriptNotFound(Exception):
    """対象言語の字幕が見つからない。"""


def _urlopen(request: Request, timeout: int = 12):
    try:
        return urlopen(request, timeout=timeout)
    except ssl.SSLError:
        pass
    except URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise
    return urlopen(request, timeout=timeout, context=ssl._create_unverified_context())


def _round_sec(value: float) -> float:
    return round(float(value) * 1000) / 1000


def _lang_matches(candidate: str, preferred: str) -> bool:
    c = (candidate or "").lower()
    p = (preferred or "").lower()
    return c == p or c.startswith(f"{p}-")


def _parse_timedtext_xml(xml: str) -> list[dict]:
    snippets: list[dict] = []
    for match in _P_TAG_RE.finditer(xml or ""):
        start_ms = int(match.group(1))
        dur_ms = int(match.group(2))
        inner = match.group(3)
        parts = _S_TAG_RE.findall(inner)
        text = "".join(parts) if parts else _TAG_RE.sub("", inner)
        text = unescape(text).strip()
        if not text:
            continue
        snippets.append(
            {
                "start": _round_sec(start_ms / 1000),
                "duration": _round_sec(max(dur_ms / 1000, 0.1)),
                "text": text,
            }
        )
    if snippets:
        return snippets

    for match in _TEXT_TAG_RE.finditer(xml or ""):
        text = unescape(match.group(3)).strip()
        if not text:
            continue
        snippets.append(
            {
                "start": _round_sec(float(match.group(1))),
                "duration": _round_sec(max(float(match.group(2)), 0.1)),
                "text": text,
            }
        )
    return snippets


def _select_track(tracks: list[dict], languages: tuple[str, ...]) -> dict | None:
    if not tracks:
        return None
    manual = [t for t in tracks if t.get("kind") != "asr"]
    auto = [t for t in tracks if t.get("kind") == "asr"]
    for pool in (manual, auto):
        for lang in languages:
            for track in pool:
                if _lang_matches(str(track.get("languageCode") or ""), lang):
                    return track
    return (manual or auto or [None])[0]


def _cache_path(video_id: str) -> Path:
    return CACHE_DIR / f"{video_id}.json"


def _read_cache(video_id: str) -> dict | None:
    path = _cache_path(video_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("snippets"):
        return None
    return data


def _write_cache(video_id: str, payload: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(video_id).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("failed to cache youtube transcript for %s", video_id)


def _public_tracks(tracks: list[dict]) -> list[dict]:
    out = []
    for track in tracks or []:
        base_url = track.get("baseUrl")
        if not base_url:
            continue
        out.append(
            {
                "languageCode": str(track.get("languageCode") or ""),
                "kind": str(track.get("kind") or ""),
                "baseUrl": str(base_url),
            }
        )
    return out


def _fetch_caption_tracks(video_id: str, client: dict) -> list[dict]:
    payload = {"context": client["context"], "videoId": video_id}
    request = Request(
        INNERTUBE_PLAYER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": client["user_agent"],
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="POST",
    )
    try:
        with _urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise TranscriptRateLimited("YouTube へのリクエストが制限されています。") from exc
        logger.info("innertube %s HTTP %s for %s", client["name"], exc.code, video_id)
        return []
    except (OSError, URLError, json.JSONDecodeError) as exc:
        logger.info("innertube %s failed for %s: %s", client["name"], video_id, exc)
        return []

    tracks = (
        (data.get("captions") or {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks")
        or []
    )
    return tracks if isinstance(tracks, list) else []


def _extract_json_object(html: str, marker: str) -> dict | None:
    start = html.find(marker)
    if start < 0:
        return None
    start = html.find("{", start)
    if start < 0:
        return None
    depth = 0
    for index, char in enumerate(html[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(html[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return data if isinstance(data, dict) else None
    return None


def _tracks_from_player_response(data: dict | None) -> list[dict]:
    if not isinstance(data, dict):
        return []
    tracks = (
        (data.get("captions") or {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks")
        or []
    )
    return tracks if isinstance(tracks, list) else []


def _fetch_tracks_from_watch_page(video_id: str) -> list[dict]:
    """CNN10 一覧と同じく watch HTML / pbj=1 は Render から通ることがある。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    pbj_request = Request(
        f"https://www.youtube.com/watch?v={video_id}&pbj=1&hl=en",
        headers={
            **headers,
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20260903.01.00",
        },
    )
    try:
        with _urlopen(pbj_request, timeout=12) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            player = item.get("playerResponse") or item.get("player_response")
            if isinstance(player, str):
                try:
                    player = json.loads(player)
                except json.JSONDecodeError:
                    player = None
            tracks = _tracks_from_player_response(player if isinstance(player, dict) else item)
            if tracks:
                return tracks
    except (OSError, URLError, json.JSONDecodeError, HTTPError) as exc:
        logger.info("watch pbj=1 failed for %s: %s", video_id, exc)

    watch_request = Request(
        f"https://www.youtube.com/watch?v={video_id}&hl=en",
        headers=headers,
    )
    try:
        with _urlopen(watch_request, timeout=12) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (OSError, URLError, HTTPError) as exc:
        logger.info("watch html failed for %s: %s", video_id, exc)
        return []
    if "g-recaptcha" in html:
        logger.info("watch html recaptcha for %s", video_id)
        return []
    player = _extract_json_object(html, "ytInitialPlayerResponse")
    return _tracks_from_player_response(player)


def fetch_youtube_transcript(url_or_video_id: str, languages: tuple[str, ...] = DEFAULT_LANGUAGES) -> dict:
    """InnerTube で字幕トラック URL を返す。本文はブラウザ側で timedtext を取る。"""
    video_id = extract_video_id(url_or_video_id)
    cached = _read_cache(video_id)
    if cached:
        return cached

    last_rate_limited = False
    for client in INNERTUBE_CLIENTS:
        try:
            tracks = _fetch_caption_tracks(video_id, client)
        except TranscriptRateLimited:
            last_rate_limited = True
            continue
        caption_tracks = _public_tracks(tracks)
        selected = _select_track(caption_tracks, languages)
        if not selected:
            continue
        payload = {
            "language_code": str(selected.get("languageCode") or languages[0] or "en"),
            "is_generated": selected.get("kind") == "asr",
            "snippets": [],
            "caption_tracks": caption_tracks,
        }
        logger.info(
            "youtube caption tracks fetched (%s, %d tracks) via %s",
            video_id,
            len(caption_tracks),
            client["name"],
        )
        return payload

    html_tracks = _public_tracks(_fetch_tracks_from_watch_page(video_id))
    selected = _select_track(html_tracks, languages)
    if selected:
        logger.info("youtube caption tracks fetched (%s, %d tracks) via watch html", video_id, len(html_tracks))
        return {
            "language_code": str(selected.get("languageCode") or languages[0] or "en"),
            "is_generated": selected.get("kind") == "asr",
            "snippets": [],
            "caption_tracks": html_tracks,
        }

    if last_rate_limited:
        raise TranscriptRateLimited("YouTube へのリクエストが制限されています。しばらく待ってから再試行してください。")
    raise TranscriptNotFound("日本語・英語の字幕が見つかりませんでした。")
