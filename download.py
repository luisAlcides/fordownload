#!/usr/bin/env python3
"""Simple downloader CLI using yt-dlp.

Features:
- Download video as MP4 (up to 1080p)
- Extract audio as MP3 (requires ffmpeg)
- Basic argument parsing and options builder (used by tests)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Any, Callable, Optional

try:
    import yt_dlp
except Exception:  # pragma: no cover - import error reported at runtime
    yt_dlp = None


def build_ydl_opts(args: argparse.Namespace) -> Dict[str, Any]:
    """Build yt-dlp options dict from parsed args.

    This function is kept pure so tests can verify options without network.
    """
    outtmpl = os.path.join(args.output, '%(title)s.%(ext)s') if args.output else '%(title)s.%(ext)s'

    common_opts: Dict[str, Any] = {
        'outtmpl': outtmpl,
        'noplaylist': not args.playlist,
        'quiet': False,
        'no_warnings': True,
        'ignoreerrors': True,
    }

    if args.format == 'mp4':
        # Prefer best video up to 1080p + best audio, fallback to best
        common_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        # Ensure postprocessors will mux if necessary (yt-dlp does this automatically when merging)
    elif args.format == 'mp3':
        common_opts['format'] = 'bestaudio/best'
        common_opts['postprocessors'] = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': str(args.quality or 192),
            }
        ]
    else:
        # generic: let yt-dlp decide
        common_opts['format'] = 'best'

    if args.overwrite:
        common_opts['outtmpl'] = outtmpl
    else:
        # don't overwrite existing files
        common_opts['nopart'] = False

    # progress hooks can be added if not quiet
    return common_opts


def download(urls: List[str], args: argparse.Namespace, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
    """Download the given URLs using yt-dlp and the provided args.

    This performs the actual network call. It will raise if yt_dlp is not installed.
    """
    if yt_dlp is None:
        raise RuntimeError('yt-dlp is required. Install with `pip install yt-dlp`')

    opts = build_ydl_opts(args)

    # progress hook - forward to callback when provided, otherwise print to stdout
    def _progress(d: Dict[str, Any]):
        try:
            if progress_callback:
                progress_callback(d)
                return
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes')
                if total and downloaded:
                    pct = downloaded / total * 100
                    print(f"Downloading {d.get('filename', '')}: {pct:.1f}%", end='\r')
            elif status == 'finished':
                print(f"\nFinished: {d.get('filename')}")
        except Exception:
            # ensure progress hook never raises
            pass

    opts['progress_hooks'] = [_progress]

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download(urls)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Descargar videos y audio (mp3/mp4) usando yt-dlp')
    parser.add_argument('urls', nargs='+', help='URLs de video o lista de reproducción')
    parser.add_argument('-o', '--output', default='.', help='Directorio de salida')
    parser.add_argument('-f', '--format', choices=['mp4', 'mp3'], default='mp4', help='Formato de salida')
    parser.add_argument('--quality', type=int, help='Calidad de audio para mp3 (kbps)')
    parser.add_argument('--playlist', action='store_true', help='Permitir descargar listas de reproducción')
    parser.add_argument('--overwrite', action='store_true', help='Sobrescribir archivos existentes')

    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        download(args.urls, args)
    except Exception as e:
        print('Error:', e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
