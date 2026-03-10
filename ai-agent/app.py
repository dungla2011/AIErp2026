import sys
import os
from ui.css import custom_css
from ui.gradio_app import create_gradio_ui

sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    demo = create_gradio_ui()
    print("\n🚀 Launching AI ERP & RAG Assistant...")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )