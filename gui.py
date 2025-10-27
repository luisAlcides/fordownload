from __future__ import annotations

import sys
import re
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets
from download import download


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)
    progress = QtCore.Signal(dict)

    def __init__(self, urls: List[str], output: str, fmt: str, quality: Optional[int], playlist: bool = False):
        super().__init__()
        self.urls = urls
        self.output = output
        self.fmt = fmt
        self.quality = int(quality) if quality else 192
        self.playlist = bool(playlist)
        self.proc: Optional[subprocess.Popen] = None

    @QtCore.Slot()
    def run(self) -> None:
        try:
            # progress callback to translate yt-dlp progress dicts into signals
            def progress_cb(d: dict) -> None:
                try:
                    status = d.get('status')
                    if status == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate')
                        downloaded = d.get('downloaded_bytes') or d.get('downloaded_bytes_estimate')
                        try:
                            percent = int(downloaded / total * 100) if total and downloaded else 0
                        except Exception:
                            percent = 0
                        filename = d.get('filename') or ''
                        self.progress.emit({'status': 'downloading', 'filename': filename, 'percent': percent})
                    elif status == 'finished':
                        filename = d.get('filename') or ''
                        self.progress.emit({'status': 'finished', 'filename': filename})
                except Exception:
                    # ensure callback never raises into download
                    pass

            # Build a minimal argparse.Namespace compatible with download.build_ydl_opts
            args = argparse.Namespace(
                output=self.output,
                format=self.fmt,
                quality=self.quality,
                playlist=self.playlist,
                overwrite=False,
            )

            # Call the shared download logic from download.py (runs in this thread)
            download(self.urls, args, progress_callback=progress_cb)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class MainWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('ForDownload')
        self.resize(720, 340)

        layout = QtWidgets.QVBoxLayout(self)

        self.url_edit = QtWidgets.QPlainTextEdit()
        self.url_edit.setPlaceholderText('Pegue una o varias URLs, una por línea')
        layout.addWidget(self.url_edit)

        form = QtWidgets.QHBoxLayout()
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(['mp4', 'mp3'])
        form.addWidget(QtWidgets.QLabel('Formato:'))
        form.addWidget(self.format_combo)

        self.quality_spin = QtWidgets.QSpinBox()
        self.quality_spin.setRange(64, 320)
        self.quality_spin.setValue(192)
        form.addWidget(QtWidgets.QLabel('Quality (kbps):'))
        form.addWidget(self.quality_spin)

        # Playlist checkbox: when checked, treat entered URLs as playlist(s)
        self.playlist_chk = QtWidgets.QCheckBox('Playlist')
        form.addWidget(self.playlist_chk)

        self.output_edit = QtWidgets.QLineEdit(str(Path.cwd()))
        out_btn = QtWidgets.QPushButton('...')
        out_btn.clicked.connect(self.choose_output)
        form.addWidget(QtWidgets.QLabel('Output:'))
        form.addWidget(self.output_edit)
        form.addWidget(out_btn)
        layout.addLayout(form)

        btns = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton('Iniciar')
        self.clear_btn = QtWidgets.QPushButton('Limpiar')
        btns.addWidget(self.start_btn)
        btns.addWidget(self.clear_btn)
        layout.addLayout(btns)

        progress_layout = QtWidgets.QHBoxLayout()
        self.file_label = QtWidgets.QLabel('')
        self.file_label.setMinimumWidth(320)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.file_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.start_btn.clicked.connect(self.start)
        self.clear_btn.clicked.connect(self.clear_ui)

        self.worker: Optional[Worker] = None
        self.worker_thread: Optional[QtCore.QThread] = None

    def choose_output(self) -> None:
        dirpath = QtWidgets.QFileDialog.getExistingDirectory(self, 'Seleccionar directorio', str(Path.cwd()))
        if dirpath:
            self.output_edit.setText(dirpath)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def start(self) -> None:
        raw = self.url_edit.toPlainText().strip()
        if not raw:
            self.append_log('No hay URLs')
            return
        urls = [line.strip() for line in raw.splitlines() if line.strip()]

        output_dir = self.output_edit.text()
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.append_log(f'No se pudo crear el directorio: {e}')
            return

        fmt = self.format_combo.currentText()
        quality = int(self.quality_spin.value()) if fmt == 'mp3' else None

        playlist = bool(self.playlist_chk.isChecked()) if hasattr(self, 'playlist_chk') else False
        self.worker = Worker(urls, output_dir, fmt, quality, playlist)
        self.worker_thread = QtCore.QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.start_btn.setEnabled(False)
        self.append_log('Iniciando descarga...')
        self.worker_thread.start()

    def _on_finished(self) -> None:
        self.append_log('Tarea finalizada')
        self.start_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.file_label.setText('')

    def _on_error(self, message: str) -> None:
        self.append_log('Error: ' + message)

    @QtCore.Slot(dict)
    def _on_progress(self, d: dict) -> None:
        status = d.get('status')
        if status == 'downloading':
            filename = d.get('filename') or ''
            pct = int(d.get('percent') or 0)
            self.progress_bar.setValue(pct)
            self.file_label.setText(filename)
            self.append_log(f'{filename}: {pct}%')
        elif status == 'finished':
            filename = d.get('filename') or ''
            self.progress_bar.setValue(100)
            self.file_label.setText(filename)
            self.append_log(f'Finished: {filename}')

    def clear_ui(self) -> None:
        self.log.clear()
        self.progress_bar.setValue(0)
        self.file_label.setText('')


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
