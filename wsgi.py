"""Gunicorn / Render 用 WSGI エントリポイント。"""
from gevent import monkey

monkey.patch_all()

from flask_app import create_app

application = create_app()

# debate の Whisper 文字起こし用 OS スレッドプールをワーカー起動時に初期化
try:
    from debate.transcription_jobs import _get_pool

    _get_pool()
except Exception:
    pass
