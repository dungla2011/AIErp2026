class ImageEmbeddingClient(BaseEmbedding):

    def __init__(self, model):
        self.model = model

    def embed_query(self, image_bytes):
        return self.model.encode(image_bytes)

    def embed_documents(self, images):
        return [self.model.encode(img) for img in images]