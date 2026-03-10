class EmbeddingFactory:

    @staticmethod
    def create_text_embedding(model_name: str):
        return OllamaTextEmbedding(model_name)

    @staticmethod
    def create_image_embedding(model_name: str):
        return ImageEmbeddingClient(model_name)

    @staticmethod
    def create_audio_embedding(model_name: str):
        return AudioEmbeddingClient(model_name)