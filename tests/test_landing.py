import unittest
from unittest.mock import patch

import gradio as gr
from fastapi.testclient import TestClient
from app import create_app


class LandingTests(unittest.TestCase):
    def test_home_brand_and_workbench_routes(self):
        with gr.Blocks() as demo:
            gr.Markdown('Workbench route test')
        with patch('app.build_page', return_value=demo):
            with TestClient(create_app()) as client:
                home = client.get('/')
                self.assertEqual(home.status_code, 200)
                self.assertIn('立即体验', home.text)
                self.assertIn('href="/workbench/"', home.text)
                icon = client.get('/brand/objectlift-icon-concept-v1.png')
                self.assertEqual(icon.status_code, 200)
                self.assertEqual(icon.headers['content-type'], 'image/png')
                self.assertEqual(client.get('/favicon.ico').status_code, 200)
                self.assertEqual(client.get('/workbench/').status_code, 200)
                self.assertEqual(client.get('/workbench/config').status_code, 200)
