import gradio as gr
import traceback
import config

from ui.chat_interface import ChatInterface
from knowledge.ingestion.document_manager import DocumentManager

from ai_core.graph.builder import create_agent_graph
from ai_core.models.chat.llm_router import LLMRouter

from ai_core.agents.rag_system import RAGSystem

from log_system.logger import get_logger



logger = get_logger(__name__)


def create_gradio_ui():

    logger.info("Initializing AI Agent System")

    try:

        # LLM Router
        llm_router = LLMRouter(config)

        # Default model
        llm = llm_router.get_role_model(
            config.MEDIUM_MODEL,
            config.MEDIUM_TEMPERATURE
        )
        # =========================
        # LLM Router
        # =========================
        # Tool registry (tuỳ project)
        tools_list = []

        # Build LangGraph
        agent_graph = create_agent_graph(llm, tools_list)

        # Chat interface dùng graph
        chat_interface = ChatInterface(agent_graph)

        # =========================
        # RAG system (documents tab)
        # =========================
        # RAG chỉ dùng cho document ingestion
        rag_system = RAGSystem()
        rag_system.initialize()

        doc_manager = DocumentManager(rag_system)

    except Exception as e:

        logger.error("Failed to initialize AI system")
        logger.error(str(e))
        raise e

    # =========================
    # DOCUMENT HELPERS
    # =========================

    def format_file_list():

        try:
            files = doc_manager.get_markdown_files()
            if not files:
                return "📭 No documents available in the knowledge base"

            return "\n".join(files)

        except Exception as e:

            logger.error("Failed to read file list")
            logger.error(str(e))

            return "❌ Error reading documents"

    # =========================
    # UPLOAD DOCUMENTS
    # =========================

    def upload_handler(files, progress=gr.Progress()):

        try:

            if not files:
                return None, format_file_list()

            file_paths = [f for f in files]

            logger.info(f"Uploading {len(file_paths)} files")

            added, skipped = doc_manager.add_documents(
                file_paths,
                progress_callback=lambda p, desc: progress(p, desc=desc)
            )

            logger.info(f"Documents added={added} skipped={skipped}")

            gr.Info(f"✅ Added: {added} | Skipped: {skipped}")

            return None, format_file_list()

        except Exception as e:

            logger.error("Upload failed")
            logger.error(traceback.format_exc())

            gr.Warning("❌ Document upload failed")

            return None, format_file_list()

    # =========================
    # CLEAR DOCUMENTS
    # =========================

    def clear_handler():

        try:

            logger.info("Clearing knowledge base")

            doc_manager.clear_all()

            gr.Info("🗑️ Removed all documents")

            return format_file_list()

        except Exception as e:

            logger.error("Failed clearing documents")
            logger.error(traceback.format_exc())

            return format_file_list()

    # =========================
    # CHAT HANDLER (STREAMING)
    # =========================

    def chat_handler(message, history):

        logger.info(f"User message: {message}")

        try:

            if history is None:
                history = []

            # call ChatInterface streaming
            for chunk in chat_interface.chat(message, history):

                yield chunk

            logger.info("Response streaming completed")

        except Exception:

            logger.error("Chat error")
            logger.error(traceback.format_exc())

            yield "❌ System error. Please try again."

    # =========================
    # CLEAR CHAT
    # =========================

    def clear_chat_handler():

        try:

            logger.info("Chat session cleared")

            chat_interface.clear_session()

        except Exception:

            logger.warning("Failed clearing chat session")

    # =========================
    # UI
    # =========================

    with gr.Blocks(title="Agentic RAG") as demo:

        with gr.Tab("Documents"):

            gr.Markdown("## Add New Documents")

            files_input = gr.File(
                label="Upload PDF or Markdown",
                file_count="multiple",
                type="filepath",
                height=200
            )

            add_btn = gr.Button(
                "Add Documents",
                variant="primary"
            )

            gr.Markdown("## Current Documents")

            file_list = gr.Textbox(
                value=format_file_list(),
                interactive=False,
                lines=10
            )

            with gr.Row():

                refresh_btn = gr.Button("Refresh")

                clear_btn = gr.Button(
                    "Clear All",
                    variant="stop"
                )

            add_btn.click(
                upload_handler,
                inputs=[files_input],
                outputs=[files_input, file_list],
                show_progress="corner"
            )

            refresh_btn.click(
                format_file_list,
                None,
                file_list
            )

            clear_btn.click(
                clear_handler,
                None,
                file_list
            )

        # =========================
        # CHAT TAB
        # =========================

        with gr.Tab("Chat"):

            chatbot = gr.Chatbot(
                height=600,
                placeholder="Ask anything about your documents"
            )

            chatbot.clear(clear_chat_handler)

            gr.ChatInterface(
                fn=chat_handler,
                chatbot=chatbot
            )

    logger.info("Gradio UI created successfully")

    return demo