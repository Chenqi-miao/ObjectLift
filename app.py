import os

os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')

from ui.library_page import build_page

if __name__ == '__main__':
    build_page().launch(server_name=os.getenv('OBJECTLIFT_HOST', '127.0.0.1'),
                        server_port=int(os.getenv('OBJECTLIFT_PORT', '7860')),
                        share=False, max_file_size='300mb')
