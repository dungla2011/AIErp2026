# Nếu RAG hoạt động
# Output:
# 
# ERP accounting integrates finance module...
# ----------------------------------------
# ERP system provides financial reporting...
# ----------------------------------------

from knowledge.retrieval.hybrid_search_engine import HybridSearchEngine
from knowledge.stores.vector_store.vector_db_manager import VectorDbManager
import config

vector_db = VectorDbManager()

collection = vector_db.get_collection(config.CHILD_COLLECTION)

search_engine = HybridSearchEngine(collection)

docs = search_engine.search("ERP accounting")

print("\nSearch Results:\n")

for i, doc in enumerate(docs):

    print("Result", i+1)

    try:
        print(doc.page_content[:200])
    except:
        print(doc)

    print("-"*40)