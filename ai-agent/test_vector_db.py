# Nếu ingestion thành công
# Output:
# 		Collection object: <QdrantCollection ...>
# 		Total vectors: 325
# 		Nghĩa là:
# 				325 chunks đã lưu
# 				Nếu chưa ingest
# 
# Output:
# 		Total vectors: 0
# 		Nghĩa là:
# 				vector DB đang trống

from knowledge.stores.vector_store.vector_db_manager import VectorDbManager
import config

vector_db = VectorDbManager()

collection = vector_db.get_collection(config.CHILD_COLLECTION)

print("Collection object:", collection) # Kiểm tra vector DB hoạt động

# Lấy Qdrant client
client = collection.client

# Lấy tên collection
collection_name = collection.collection_name

# Đếm số vectors
info = client.get_collection(collection_name)
 
print("Total vectors:", info.points_count) # Kiểm tra collection có dữ liệu chưa