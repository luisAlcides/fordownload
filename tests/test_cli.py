import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from download import parse_args, build_ydl_opts


def test_build_opts_mp4(tmp_path):
    argv = ['https://example.com/watch?v=1', '-o', str(tmp_path), '-f', 'mp4']
    args = parse_args(argv)
    opts = build_ydl_opts(args)
    assert 'format' in opts
    assert '1080' in opts['format'] or 'best' in opts['format']
    assert opts['outtmpl'].startswith(str(tmp_path))


def test_build_opts_mp3(tmp_path):
    argv = ['https://example.com/watch?v=2', '-o', str(tmp_path), '-f', 'mp3', '--quality', '256']
    args = parse_args(argv)
    opts = build_ydl_opts(args)
    assert opts['format'].startswith('bestaudio')
    pp = opts.get('postprocessors')
    assert pp and pp[0]['preferredcodec'] == 'mp3'
    assert '256' in pp[0]['preferredquality']
