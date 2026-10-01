import chromadb
from chromadb.utils import embedding_functions
import os

def initialize_vector_store():
    """
    Initializes ChromaDB vector store with sample audit reports,
    generates embeddings, and enables semantic search.
    """
    # Create persistent ChromaDB client
    db_path = os.path.join(os.path.dirname(__file__), "../../chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    # Use standard default embedding function
    sentence_transformer_ef = embedding_functions.DefaultEmbeddingFunction()
    
    # Get or create collection
    collection = client.get_or_create_collection(
        name="hospital_reports",
        embedding_function=sentence_transformer_ef
    )
    
    # Sample reports/documents to index
    sample_reports = [
        {
            "id": "doc_icu_01",
            "text": "ICU Adult Quarterly Maintenance Audit: High-demand equipment experienced a 12% increase in unscheduled repairs during Q1. Preventive maintenance schedules were updated to bi-weekly checks.",
            "department": "ICU Adult",
            "type": "Audit Report"
        },
        {
            "id": "doc_er_01",
            "text": "Emergency Room Sanitation Protocol: Advanced sanitation response time averaged 45 minutes. Priority URGENT tickets decreased by 18% after introducing automated dispatch routines.",
            "department": "Emergency Room",
            "type": "Protocol Update"
        },
        {
            "id": "doc_surg_01",
            "text": "Surgical Center Safety Vistoria: All sterilization equipment passed safety compliance inspections. Replacement of HVAC air filters is scheduled for next month to maintain laminar airflow standards.",
            "department": "Surgical Center",
            "type": "Safety Inspection"
        },
        {
            "id": "doc_ped_01",
            "text": "Pediatrics Operational Efficiency: Facility requests in Pediatrics had the lowest average response time (28 minutes). Staff training on medical device handling reduced user-error tickets by 30%.",
            "department": "Pediatrics",
            "type": "Efficiency Summary"
        }
    ]
    
    # Index documents if collection is empty
    if collection.count() == 0:
        ids = [doc["id"] for doc in sample_reports]
        documents = [doc["text"] for doc in sample_reports]
        metadatas = [{"department": doc["department"], "type": doc["type"]} for doc in sample_reports]
        
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        print("✅ Sample reports successfully embedded and indexed in ChromaDB.")
    else:
        print(f"ℹ️ ChromaDB collection already loaded with {collection.count()} documents.")

    return collection

def query_vector_store(query_text, n_results=2):
    """
    Queries ChromaDB to retrieve relevant context snippets for a user prompt.
    """
    collection = initialize_vector_store()
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    
    context_chunks = results['documents'][0] if results['documents'] else []
    return context_chunks

if __name__ == "__main__":
    print("Testing Vector Store initialization...")
    collection = initialize_vector_store()
    
    # Test query
    test_query = "What are the audit findings for the ICU Adult?"
    retrieved = query_vector_store(test_query)
    print(f"\n🔍 Query: '{test_query}'")
    print("📌 Retrieved Context:")
    for i, chunk in enumerate(retrieved, 1):
        print(f"  {i}. {chunk}")