class RerankerFactory:

    @staticmethod
    def create_reranker(model_name: str):
        return CrossEncoderReranker(model_name)