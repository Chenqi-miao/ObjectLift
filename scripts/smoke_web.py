"""Exercise the running local web API with a generated transparent image."""
import tempfile
from pathlib import Path

from PIL import Image
from gradio_client import Client, handle_file


def main():
    client = Client('http://127.0.0.1:7860', verbose=False, httpx_kwargs={'trust_env': False})
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.png'
        Image.new('RGBA', (64, 48), (0, 140, 100, 128)).save(path)
        uploaded = client.predict(handle_file(str(path)), api_name='/on_upload')
        assert list(uploaded[3:5]) == [64, 48], uploaded
        cropped = client.predict(5, 5, 40, 30, 0, api_name='/do_crop')
        with Image.open(cropped[0]) as image:
            assert image.size == (35, 25), image.size
        assert Path(cropped[1]).is_file()
        print('PASS: HTTP upload, session state, crop and downloadable PNG.')


if __name__ == '__main__':
    main()
