from qdrant_client import QdrantClient, models
from typing import List, Optional, Dict
import logging
from datetime import datetime, timedelta, timezone
import uuid

class VectorStoreManager:
    def __init__(self, retention_hours: int = 24):
        self.client = QdrantClient(
            host="qdrant",
            port=6333,
            grpc_port=6334,
            prefer_grpc=True
        )
        self.collection_name = "documents"
        self.retention_hours = retention_hours
        self._init_collection()
        
        # Initialize FastEmbed model
        self.client.set_model(
            embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_class="fastembed",
            cache_dir="/models",
            threads=4
        )

    def _init_collection(self):
        """Initialize collection with FastEmbed dimensions"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_exists = any(col.name == self.collection_name for col in collections.collections)
            
            if not collection_exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=384,  # all-MiniLM-L6-v2 output dimension
                        distance=models.Distance.COSINE
                    )
                )
                
                # Create index for session filtering
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="session_id",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                # Create index for expires_at field for manual cleanup
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="expires_at",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
                
                logging.info(f"Collection {self.collection_name} initialized")
        except Exception as e:
            logging.error(f"Collection init error: {str(e)}")
            raise

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Use Qdrant's FastEmbed integration"""
        return self.client.encode_text(texts)

    def store_documents(self, documents: List[Dict[str, str]], session_id: Optional[str] = None):
        """Store documents with metadata in batches"""
        if not documents:
            return

        batch_size = 100
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.retention_hours)

        for batch_idx in range(0, len(documents), batch_size):
            batch = documents[batch_idx:min(batch_idx + batch_size, len(documents))]
            
            try:
                embeddings = self._generate_embeddings([doc["text"] for doc in batch])
                
                points = [
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload={
                            "text": doc["text"],
                            "source": doc.get("source", ""),
                            "session_id": session_id,
                            "expires_at": expires_at.isoformat()
                        }
                    )
                    for doc, embedding in zip(batch, embeddings)
                ]

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True  # Wait for completion to ensure data is available for search
                )
            except Exception as e:
                logging.error(f"Batch {batch_idx} error: {str(e)}")

    def search(self, query: str, session_id: Optional[str] = None, top_k: int = 3) -> List[Dict[str, str]]:
        """Search with source metadata and session filtering"""
        try:
            query_embedding = self._generate_embeddings([query])[0]
            
            # Create filter if session_id is provided
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
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=filter_condition
            )
            
            search_results = [
                {"text": hit.payload["text"], "source": hit.payload.get("source", "Unknown")}
                for hit in results
            ]
            
            # Schedule cleanup of documents after search (if using the quick cleanup approach)
            # This is optional - you can also keep the documents for the full retention period
            # self.delete_session_embeddings(session_id)
            
            return search_results
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return []

    def delete_session_embeddings(self, session_id: str):
        """Remove all embeddings from a specific session"""
        if not session_id:
            return
            
        try:
            self.client.delete(
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

    def cleanup_expired(self):
        """Remove expired embeddings automatically - can be run via cron job"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="expires_at",
                                range=models.Range(lt=now)
                            )
                        ]
                    )
                ),
                wait=False
            )
            logging.info(f"Expired documents cleanup executed at {now}")
        except Exception as e:
            logging.error(f"Error in cleanup_expired: {str(e)}")

# You can set up a periodic job to run this cleanup
if __name__ == "__main__":
    # For running cleanup via cron job
    VectorStoreManager().cleanup_expired()