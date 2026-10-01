import os
import requests
from rag.vector_store import query_vector_store

def generate_rag_response(user_query: str) -> str:
    """
    Retrieves relevant document snippets from ChromaDB and generates 
    an augmented answer using an LLM API or an enhanced fallback engine.
    """
    query_lower = user_query.strip().lower()

    # 1. Handle common greetings and conversational prompts gracefully
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'who are you']
    if query_lower in greetings or len(query_lower) < 3:
        return (
            "Hello! I am your AI Hospital Operational Analyst.\n\n"
            "I can help you analyze internal audit reports, equipment maintenance records, "
            "and facility protocols.\n\n"
            "**Try asking questions like:**\n"
            "- *What are the audit findings for the ICU Adult?*\n"
            "- *How is the Emergency Room handling sanitation response times?*\n"
            "- *What happened in Pediatrics regarding equipment?*"
        )

    # 2. Retrieve context chunks from Vector Store
    context_chunks = query_vector_store(user_query, n_results=2)
    context_text = "\n".join([f"- {chunk}" for chunk in context_chunks]) if context_chunks else ""

    # 3. Check for Ollama or API endpoints
    ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434/api/generate")
    
    prompt = f"""You are an expert AI Data Analyst for hospital operations.
Answer the user query concisely based ONLY on the provided document context.

DOCUMENT CONTEXT:
{context_text}

USER QUERY: {user_query}

ANSWER:"""

    try:
        response = requests.post(
            ollama_url,
            json={"model": "qwen2.5-coder", "prompt": prompt, "stream": False},
            timeout=2
        )
        if response.status_code == 200:
            return response.json().get("response", "No response content from LLM.")
    except Exception:
        pass

    # 4. Enhanced Fallback Synthesizer (Generates clean natural language answers)
    if not context_chunks:
        return "I searched the internal database, but couldn't find any relevant audit reports for your query."

    formatted_response = f"Based on the internal operational records, here is what was found regarding **'{user_query}'**:\n\n"
    for idx, chunk in enumerate(context_chunks, 1):
        formatted_response += f"**Key Finding {idx}:** {chunk}\n\n"

    formatted_response += "> 💡 *Context retrieved live from ChromaDB vector store.*"
    
    return formatted_response

if __name__ == "__main__":
    test_question = "hi"
    print(generate_rag_response(test_question))