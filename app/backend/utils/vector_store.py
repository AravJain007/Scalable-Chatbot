from qdrant_client import QdrantClient, models
from typing import List, Optional, Dict
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import Config

class VectorStoreManager:
    DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    SPARSE_MODEL = "prithivida/Splade_PP_en_v1"
    def __init__(self):
        self.collection_name = "document"
        # initialize Qdrant client
        self.qdrant_client = QdrantClient(f"http://{Config.QDRANT_HOST}:{Config.QDRANT_PORT}")
        self.qdrant_client.set_model(self.DENSE_MODEL)
        # comment this line to use dense vectors only
        # self.qdrant_client.set_sparse_model(self.SPARSE_MODEL)
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=750,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False,
        )
        if not self.qdrant_client.collection_exists(self.collection_name):
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.qdrant_client.get_fastembed_vector_params(),
                # comment this line to use dense vectors only
                # sparse_vectors_config=self.qdrant_client.get_fastembed_sparse_vector_params(),  
            )

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Use Qdrant's FastEmbed integration"""
        return self.client.encode_text(texts)

    def store_documents(self, documents: List[Dict[str, str]], session_id: Optional[str] = None):
        """Store documents with metadata in batches"""
        if not documents:
            return
        
        try:
            # Process documents with chunking
            processed_docs = []
            metadata = []
            for doc in documents:
                # Split text into chunks
                chunks = self.text_splitter.split_text(doc["text"])
                for chunk in chunks:
                    processed_docs.append(chunk)
                    metadata.append({
                        "title": doc.get("title", "No Title"),
                        "source": doc.get("source", ""),
                        "session_id": session_id
                    })

            self.qdrant_client.add(
                collection_name=self.collection_name,
                documents=processed_docs,
                metadata=metadata
            )
        except Exception as e:
            logging.error(f"Storing error: {str(e)}")


    def search(self, query: str, session_id: Optional[str] = None, top_k: int = 3) -> List[Dict[str, str]]:
        """Search with source metadata and optional session filtering"""
        try:
            filter_condition = None
            if session_id:
                filter_condition = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=session_id)
                        )
                    ]
                )
            
            results = self.qdrant_client.query(
                collection_name=self.collection_name,
                query_text=query,
                limit=top_k,
                query_filter=filter_condition
            )
            
            search_results = [
                {
                    "title": result.metadata.get("title", ""),  # Title from metadata
                    "text": result.document,                        # Text from the main document field
                    "source": result.metadata.get("source", "")     # Source from metadata
                }
                for result in results  # Iterate over each QueryResponse
            ]
            
            return search_results
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return []

    def delete_session_embeddings(self, session_id: str):
        """Remove all embeddings from a specific session"""
        if not session_id:
            return
            
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="session_id",
                                match=models.MatchValue(value=session_id)
                            )
                        ]
                    )
                ),
                wait=False  # Don't wait for completion to improve performance
            )
            logging.info(f"Scheduled deletion of embeddings for session {session_id}")
        except Exception as e:
            logging.error(f"Error deleting session embeddings: {str(e)}")