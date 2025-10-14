from __future__ import annotations

import sys
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)
    progress = QtCore.Signal(dict)

    def __init__(self, urls: List[str], output: str, fmt: str, quality: Optional[int]):
        super().__init__()
        self.urls = urls
        self.output = output
        self.fmt = fmt
        self.quality = int(quality) if quality else 192
        self.proc: Optional[subprocess.Popen] = None

    @QtCore.Slot()
    def run(self) -> None:
        try:
            cmd = [sys.executable, '-m', 'yt_dlp', '--newline', '--ignore-errors', '--no-playlist']
            outtmpl = str(Path(self.output) / '%(title)s.%(ext)s')
            cmd += ['-o', outtmpl]
            if self.fmt == 'mp4':
                fmt_expr = (
                    'bestvideo[ext=mp4][height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]'
                    '/bestvideo[height<=1080]+bestaudio/best[height<=1080]'
                )
                cmd += ['-f', fmt_expr, '--merge-output-format', 'mp4']
            elif self.fmt == 'mp3':
                cmd += ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', f'{self.quality}K']
            else:
                cmd += ['-f', 'best']
            cmd += self.urls

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            current_file = ''
            dest_re = re.compile(r"\[download\]\s+Destination:\s+(.*)")
            prog_re = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d)?)%")

            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                line = line.rstrip('\n')
                m_dest = dest_re.search(line)
                if m_dest:
                    current_file = m_dest.group(1)
                m = prog_re.search(line)
                if m:
                    try:
                        percent = int(float(m.group(1)))
                    except Exception:
                        percent = 0
                    self.progress.emit({'status': 'downloading', 'filename': current_file, 'percent': percent})

            ret = self.proc.wait()
            if ret == 0:
                self.progress.emit({'status': 'finished', 'filename': current_file})
            else:
                raise RuntimeError(f'yt-dlp exited with code {ret}')
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

        self.worker = Worker(urls, output_dir, fmt, quality)
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
