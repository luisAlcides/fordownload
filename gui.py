from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import List

from PySide6 import QtCore, QtWidgets

from download import parse_args, build_ydl_opts, download


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, urls: List[str], args: object):
        super().__init__()
        self._urls = urls
        self._args = args

    @QtCore.Slot()
    def run(self):
        try:
            # download() expects args namespace
            download(self._urls, self._args)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ForDownload')
        self.resize(600, 200)

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
        self.stop_btn = QtWidgets.QPushButton('Detener')
        self.stop_btn.setEnabled(False)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        layout.addLayout(btns)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

        self._thread = None
        self._worker = None

    def choose_output(self):
        dirpath = QtWidgets.QFileDialog.getExistingDirectory(self, 'Seleccionar directorio', str(Path.cwd()))
        if dirpath:
            self.output_edit.setText(dirpath)

    def append_log(self, text: str):
        self.log.appendPlainText(text)

    def start(self):
        raw = self.url_edit.toPlainText().strip()
        if not raw:
            self.append_log('No hay URLs')
            return
        urls = [line.strip() for line in raw.splitlines() if line.strip()]

        # build args namespace similar to CLI
        class Args:
            pass

        args = Args()
        args.output = self.output_edit.text()
        args.format = self.format_combo.currentText()
        args.quality = self.quality_spin.value()
        args.playlist = False
        args.overwrite = False

        # run in background thread
        self._worker = Worker(urls, args)
        self._worker_thread = QtCore.QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.append_log('Iniciando descarga...')
        self._worker_thread.start()

    def stop(self):
        # there is no clean stop implemented for yt-dlp in this simple GUI.
        self.append_log('Detener no implementado en esta versión')

    def _on_finished(self):
        self.append_log('Tarea finalizada')
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_error(self, message: str):
        self.append_log('Error: ' + message)


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
