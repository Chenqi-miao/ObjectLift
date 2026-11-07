"""Bounded local MP4 decoding; timestamps come from selected decoded frames."""
import json
import math
import os
import re
import subprocess
from pathlib import Path


def run(tool, arguments):
    bundled = sorted((Path(__file__).resolve().parents[1] / 'tools' / 'ffmpeg').glob(f'*/bin/{tool}.exe'))
    executable = os.getenv('OBJECTLIFT_' + tool.upper()) or (str(bundled[0]) if bundled else tool)
    try:
        return subprocess.run([executable, *map(str, arguments)], capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=180, check=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except FileNotFoundError as exc:
        raise ValueError(f'未找到 {tool}，请安装 FFmpeg 或配置 OBJECTLIFT_{tool.upper()}。') from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('视频处理超时，请使用更小的视频。') from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError('视频解码失败：' + exc.stderr[-1000:]) from exc


def extract_video(source, output):
    info = json.loads(run('ffprobe', ['-v', 'error', '-show_format', '-show_streams',
                                    '-of', 'json', source]).stdout)
    streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
    if not streams or streams[0].get('codec_name') != 'h264':
        raise ValueError('仅支持 H.264 编码的 MP4 视频。')
    if 'mp4' not in info.get('format', {}).get('format_name', '').split(','):
        raise ValueError('文件不是 MP4 容器。')
    stream = streams[0]
    duration = float(info['format'].get('duration', 0))
    if not math.isfinite(duration) or not 0 < duration <= 180:
        raise ValueError('视频时长必须在 0 到 180 秒之间。')
    width, height = int(stream['width']), int(stream['height'])
    if not 0 < width * height <= 40_000_000:
        raise ValueError('视频画面尺寸过大或无效。')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = run('ffmpeg', ['-nostdin', '-hide_banner', '-i', source, '-map', '0:v:0',
        '-vf', "select='isnan(prev_selected_t)+gte(t-prev_selected_t,5)',scale=512:512:force_original_aspect_ratio=decrease,showinfo",
        '-fps_mode', 'vfr', '-frames:v', '37', '-an', output / 'frame-%03d.png'])
    times = [round(float(t) * 1000) for t in re.findall(r'\bpts_time:([\d.eE+\-]+)', result.stderr)]
    frames = sorted(output.glob('frame-*.png'))
    if not frames or len(frames) != len(times) or any(t < 0 for t in times):
        raise ValueError('视频抽帧或时间戳校验失败。')
    return width, height, round(duration * 1000), list(zip(frames, times))
