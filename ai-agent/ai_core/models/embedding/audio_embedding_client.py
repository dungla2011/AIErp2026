class AudioEmbeddingClient(BaseEmbedding):

    def __init__(self, model):
        self.model = model

    def embed_query(self, audio_path: str):
        return self.model.encode(audio_path)

    def embed_documents(self, audio_list):
        return [self.model.encode(a) for a in audio_list]