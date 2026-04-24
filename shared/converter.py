"""Deteccion de codec con ffprobe y conversion VP9 -> H.264 con ffmpeg."""

import shutil
import subprocess
from pathlib import Path


def get_video_codec(path: Path, config: dict) -> str:
    """Detecta el codec de video usando ffprobe."""
    ffprobe = config["conversion"]["ffprobe"]
    result = subprocess.run(
        [ffprobe, "-v", "error",
         "-select_streams", "v:0",
         "-show_entries", "stream=codec_name",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return result.stdout.strip().rstrip(",")


def convert_to_h264(src: Path, dst: Path, config: dict) -> tuple[bool, str]:
    """Convierte un video a H.264/AAC."""
    conv = config["conversion"]
    cmd = [
        conv["ffmpeg"], "-y", "-i", str(src),
        "-c:v", conv["codec"],
        "-crf", str(conv["crf"]),
        "-preset", conv.get("preset", "fast"),
        "-c:a", conv["audio_codec"],
        "-b:a", conv["audio_bitrate"],
        "-movflags", "+faststart",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr[-200:]


def convert_all(directory: Path, config: dict) -> dict:
    """Convierte todos los videos no-H.264 en un directorio. Renombra in-place."""
    videos = sorted(directory.rglob("*.mp4"))
    if not videos:
        print("No hay videos para convertir.")
        return {"copied": 0, "converted": 0, "failed": 0}

    print(f"Videos a verificar: {len(videos)}\n")
    copied, converted, failed = 0, 0, 0

    for src in videos:
        codec = get_video_codec(src, config)

        if codec == "h264":
            copied += 1
            continue

        if "vp9" in codec or "vp8" in codec or codec == "av1":
            tmp = src.with_suffix(".converting.mp4")
            print(f"  [convert] {src.name} ({codec}) ... ", end="", flush=True)
            success, err = convert_to_h264(src, tmp, config)
            if success:
                src.unlink()
                tmp.rename(src)
                print("ok")
                converted += 1
            else:
                tmp.unlink(missing_ok=True)
                print(f"ERROR: {err}")
                failed += 1
        else:
            copied += 1

    print(f"\nH.264: {copied} | Convertidos: {converted} | Fallidos: {failed}")
    return {"copied": copied, "converted": converted, "failed": failed}
