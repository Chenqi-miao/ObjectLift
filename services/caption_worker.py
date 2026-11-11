"""One-shot offline video description process; exit releases GPU memory."""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration


def load_model(path):
    processor = AutoProcessor.from_pretrained(path, local_files_only=True,
                                             min_pixels=56*56, max_pixels=224*224)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        path, local_files_only=True, torch_dtype=torch.float16 if device == 'cuda' else torch.float32,
        attn_implementation='sdpa').to(device).eval()
    return processor, model, device


def generate(request, processor, model, device):
    frames = []
    for frame in request['frames']:
        with Image.open(frame['path']) as image:
            frames.append(np.asarray(ImageOps.pad(image.convert('RGB'), (224, 224), color='black')))
    if len(frames) == 1:
        frames.append(frames[0])
    times = ', '.join(f"{(frame['timestamp_ms'] or 0)/1000:.2f}" for frame in request['frames'])
    prompt = ('请用中文简洁描述视频中可见的人物、物体、场景及画面变化。'
              '这些是按时间顺序抽取的画面，不能假设采样间发生的动作，不要猜测声音、身份或动机。'
              '只描述可观察事实，不使用精致、梦幻等主观评价。不要推断整段视频的固定人物总数；若场景变化请说明。'
              f'原视频时长 {(request["duration_ms"] or 0)/1000:.2f} 秒，实际采样时间（秒）：{times}。'
              '只输出一段不超过200字的描述；无法确定的内容明确说明。')
    is_image = request.get('media_type') == 'image'
    if is_image:
        prompt = ('请描述并分类这张图片，只输出JSON对象，包含caption字符串和tags字符串数组两个字段。'
                  'caption是一句中文客观描述，不猜测身份动机。tags最多5个，只能选择下列适用类别：'
                  '人物（人、人物绘画），动物（动物、昆虫），建筑（房屋、建筑物），自然（植物、山水、自然风景），'
                  '室内（房间、室内空间），交通（车辆、道路），食物（食品、饮料），物品（电子设备、工具、日用品、人工制品）。'
                  '标签必须对应画面主体。电子设备应选物品，不能因背景颜色选自然；有多个主体可选多个类别。'
                  'tags中只写类别名称，不要括号或解释，不要创造新类别。例如动物图片返回{"caption":"一只狗。","tags":["动物"]}；电子设备返回{"caption":"一个头盔。","tags":["物品"]}。'
                  '无法匹配预设类别或无法辨认内容时tags返回["未分类"]。不要输出Markdown。')
    messages = [{'role': 'user', 'content': [{'type': 'image' if is_image else 'video'}, {'type': 'text', 'text': prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    media = {'images': [frames[0]]} if is_image else {'videos': [np.stack(frames)]}
    inputs = processor(text=[text], **media, padding=True, return_tensors='pt').to(device)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    caption = processor.batch_decode(output[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0].strip()
    if not caption:
        raise ValueError('模型返回空描述。')
    result = {'caption': caption}
    if is_image:
        start, end = caption.find('{'), caption.rfind('}')
        result = json.loads(caption[start:end+1])
    return result


def main():
    if sys.argv[1] == '--session':
        loaded = None
        for line in sys.stdin:
            request_path, output_path = json.loads(line)
            try:
                request = json.loads(Path(request_path).read_text(encoding='utf-8'))
                if loaded is None:
                    loaded = load_model(request['model_path'])
                result = generate(request, *loaded)
            except Exception as exc:
                result = {'error': str(exc)}
            output = Path(output_path)
            temporary = output.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            temporary.replace(output)
    else:
        request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        result = generate(request, *load_model(request['model_path']))
        Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
