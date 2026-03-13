from pathlib import Path
import shutil
import config
from utils import pdfs_to_markdowns

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        
    def add_documents(self, document_paths, progress_callback=None):
        if not document_paths:
            return 0, 0
            
        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]
        
        if not document_paths:
            return 0, 0
            
        added = 0
        skipped = 0
            
        for i, doc_path in enumerate(document_paths):
            if progress_callback:
                progress_callback((i + 1) / len(document_paths), f"Processing {Path(doc_path).name}")
                
            doc_name = Path(doc_path).stem
            md_path = self.markdown_dir / f"{doc_name}.md"
            
            if md_path.exists():
                skipped += 1
                continue
                
            try:
                print("🔥 Ingest pipeline started for:", doc_path)    

                if Path(doc_path).suffix.lower() == ".md":
                    print("📄 Copying markdown file:", doc_path)    
                    shutil.copy(doc_path, md_path)
                    print("🔥 Markdown saved to:", md_path)
                else:
                    print("📄 Converting PDF to Markdown:", doc_path)

                    # Gọi hàm convert như cũ
                    generated_files = pdfs_to_markdowns(str(doc_path), overwrite=False)

                    # Tìm file markdown vừa được tạo
                    if not generated_files:
                        print("❌ No markdown file returned from converter")
                        skipped += 1
                        continue

                    generated_md_path = Path(generated_files[0])

                    # Di chuyển file về markdown_dir nếu cần
                    if generated_md_path.exists():
                        shutil.move(str(generated_md_path), str(md_path))
                        print("🔥 Markdown moved to:", md_path)
                    else:
                        print("❌ Generated markdown file not found:", generated_md_path)
                        skipped += 1
                        continue           
                parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(md_path)

                print("🔎 Parent chunks:", len(parent_chunks))
                print("🔎 Child chunks:", len(child_chunks))
                
                if not child_chunks:
                    print("⚠️ No child chunks created!")
                    skipped += 1
                    continue
                
                collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
                collection.add_documents(child_chunks)
                self.rag_system.parent_store.save_many(parent_chunks)

                print("✅ Successfully indexed:", doc_name)
                
                added += 1
                
            except Exception as e:
                print(f"Error processing {doc_path}: {e}")
                skipped += 1
            
        return added, skipped
    
    def get_markdown_files(self):
        if not self.markdown_dir.exists():
            return []
        return sorted([p.name.replace(".md", ".pdf") for p in self.markdown_dir.glob("*.md")])
    
    def clear_all(self):
        """Clear all documents and databases (markdown, parent_store, qdrant)"""
        errors = []
        
        # Clear markdown files
        try:
            if self.markdown_dir.exists():
                shutil.rmtree(self.markdown_dir)
            self.markdown_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Cleared markdown directory: {self.markdown_dir}")
        except Exception as e:
            error_msg = f"Failed to clear markdown directory: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
        
        # Clear parent store (document chunks database)
        try:
            self.rag_system.parent_store.clear_store()
            print(f"✓ Cleared parent_store database")
        except Exception as e:
            error_msg = f"Failed to clear parent_store: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
        
        # Clear vector database (qdrant)
        try:
            self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)
            print(f"✓ Deleted Qdrant collection: {self.rag_system.collection_name}")
        except Exception as e:
            error_msg = f"Failed to delete Qdrant collection: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
        
        # Recreate vector collection
        try:
            self.rag_system.vector_db.create_collection(self.rag_system.collection_name)
            print(f"✓ Created new Qdrant collection: {self.rag_system.collection_name}")
        except Exception as e:
            error_msg = f"Failed to create new Qdrant collection: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
        
        if errors:
            raise Exception(f"Clear operation completed with errors: {'; '.join(errors)}")