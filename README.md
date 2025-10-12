# ForDownload

Pequeña utilidad para descargar vídeos (MP4 hasta 1080p) y extraer audio como MP3 usando `yt-dlp` y `ffmpeg`.

Instalación (Windows PowerShell):

```powershell
python -m venv env
./env/Scripts/Activate.ps1
pip install -r requirements.txt
# Asegúrate de tener ffmpeg en el PATH (https://ffmpeg.org/download.html)
```

Uso básico:

```powershell
python download.py -f mp4 https://www.youtube.com/watch?v=xxxxxxxxxxx
python download.py -f mp3 --quality 192 https://www.youtube.com/watch?v=xxxxxxxxxxx
```

Notas:
- Esta versión inicial expone un CLI y un constructor de opciones (`build_ydl_opts`) que es fácil de testear.
- `yt-dlp` realiza el trabajo pesado. Esta herramienta envuelve `yt-dlp` con opciones orientadas a mp4 (<=1080p) y mp3.
