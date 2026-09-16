import os

from dotenv import load_dotenv
from google import genai

from src.vector_store import search


load_dotenv()


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

LLM_MODEL = "gemini-3.6-flash"


def build_context(results: list[dict]) -> str:
    """
    Convert retrieved chunks into context for the LLM.
    """

    context_parts = []

    for i, result in enumerate(results, start=1):

        context_parts.append(
            f"""
SOURCE {i}
Document: {result['document_name']}
Airport: {result['airport']}
Section: {result['section_number']}
Similarity Score: {result['score']:.4f}

Policy Content:
{result['text']}
"""
        )

    return "\n".join(context_parts)


def answer_question(
    question: str,
    airport: str | None = None,
    top_k: int = 3
) -> dict:
    """
    Retrieve relevant policy chunks and generate
    a grounded answer using Gemini.
    """

    # Retrieve relevant chunks
    results = search(
        question,
        top_k=top_k
    )

    # Optional airport filtering
    if airport:

        airport_results = [
            result
            for result in results
            if result["airport"].upper() == airport.upper()
        ]

        if airport_results:
            results = airport_results

    # Handle no retrieved results
    if not results:
        return {
            "answer": (
                "I could not find relevant information "
                "in the airport policies."
            ),
            "sources": []
        }

    # Build context from retrieved chunks
    context = build_context(results)

    # Prompt for grounded generation
    prompt = f"""
You are an Airport Operations AI Copilot.

Answer the user's question using ONLY the policy information
provided in the context below.

Rules:
1. Do not invent or assume policy information.
2. If the answer is not present in the context, say:
   "The available airport policies do not specify this."
3. Give a concise and clear answer.
4. Mention the relevant airport when applicable.
5. Include the policy source documents used.
6. If the policy requires approval or investigation,
   explicitly mention it.

User Question:
{question}

Policy Context:
{context}
"""

    # Generate answer using Gemini
    interaction = client.interactions.create(
        model=LLM_MODEL,
        input=prompt
    )

    answer = interaction.output_text

    # Prepare source information
    sources = [
        {
            "document": result["document_name"],
            "airport": result["airport"],
            "section": result["section_number"],
            "score": round(result["score"], 4)
        }
        for result in results
    ]

    return {
        "answer": answer,
        "sources": sources
    }


if __name__ == "__main__":

    question = "What is the maximum surge multiplier allowed at SFO?"

    result = answer_question(question)

    print("\nANSWER")
    print("=" * 70)
    print(result["answer"])

    print("\nSOURCES")
    print("=" * 70)

    for source in result["sources"]:

        print(
            f"- {source['document']} | "
            f"{source['airport']} | "
            f"Section {source['section']} | "
            f"Score: {source['score']}"
        )

