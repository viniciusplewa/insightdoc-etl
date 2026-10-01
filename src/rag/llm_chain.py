import os
import requests
from vector_store import query_vector_store

def generate_rag_response(user_query: str) -> str:
    """
    Retrieves relevant document snippets from ChromaDB and generates 
    an augmented answer using an LLM API or fallback reasoning engine.
    """
    # 1. Retrieve context chunks from Vector Store
    context_chunks = query_vector_store(user_query, n_results=2)
    
    context_text = "\n".join([f"- {chunk}" for chunk in context_chunks]) if context_chunks else "No specific documents found."
    
    # 2. Check for Ollama local API endpoint (e.g. http://localhost:11434)
    ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434/api/generate")
    
    prompt = f"""You are an expert AI Data Analyst for hospital operations.
Answer the user query based ONLY on the provided document context.

DOCUMENT CONTEXT:
{context_text}

USER QUERY: {user_query}

ANSWER:"""

    try:
        # Attempt connection to local Ollama instance if available
        response = requests.post(
            ollama_url,
            json={"model": "qwen2.5-coder", "prompt": prompt, "stream": False},
            timeout=3
        )
        if response.status_code == 200:
            return response.json().get("response", "No response content from LLM.")
    except Exception:
        # Fallback to local heuristic RAG engine if no local LLM service is running
        pass

    # Built-in fallback response generator using retrieved context
    formatted_response = f"**[RAG Retrieval Summary]**\nBased on internal operational records:\n\n"
    for chunk in context_chunks:
        formatted_response += f"📌 {chunk}\n\n"
    formatted_response += "*Note: Connected to ChromaDB vector store. Add OLLAMA_HOST or OpenAI API Key for full text generation.*"
    
    return formatted_response

if __name__ == "__main__":
    test_question = "What happened in Pediatrics regarding equipment?"
    print(f"❓ Question: {test_question}\n")
    response = generate_rag_response(test_question)
    print("🤖 RAG Answer:\n")
    print(response)