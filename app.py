import os
from pathlib import Path

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')

from ui.library_page import build_page

ROOT = Path(__file__).resolve().parent


def create_app():
    app = FastAPI(title='ObjectLift')
    app.mount('/brand', StaticFiles(directory=ROOT / 'assets/branding'), name='brand')

    @app.get('/', include_in_schema=False)
    def home():
        return FileResponse(ROOT / 'ui/landing.html')

    @app.get('/favicon.ico', include_in_schema=False)
    def favicon():
        return FileResponse(ROOT / 'assets/branding/objectlift-icon-concept-v1.png', media_type='image/png')

    return gr.mount_gradio_app(app, build_page(), path='/workbench', max_file_size='300mb')


if __name__ == '__main__':
    uvicorn.run(create_app(), host=os.getenv('OBJECTLIFT_HOST', '127.0.0.1'),
                port=int(os.getenv('OBJECTLIFT_PORT', '7860')))
