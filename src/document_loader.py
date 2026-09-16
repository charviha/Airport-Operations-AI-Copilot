from pathlib import Path
import re


# Path to airport policy documents
POLICY_DIR = Path("data/airport_policies")


def clean_text(text: str) -> str:
    """
    Clean policy text while preserving meaningful content.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def load_documents(policy_dir: Path = POLICY_DIR) -> list[dict]:
    """
    Load all Markdown policy documents.

    Returns:
        List of dictionaries containing:
        - document_name
        - airport
        - text
    """

    documents = []

    if not policy_dir.exists():
        raise FileNotFoundError(
            f"Policy directory not found: {policy_dir}"
        )

    for file_path in sorted(policy_dir.glob("*.md")):

        text = file_path.read_text(encoding="utf-8")

        text = clean_text(text)

        # Extract airport code from filename
        airport = file_path.name.split("_")[0].upper()

        documents.append(
            {
                "document_name": file_path.name,
                "airport": airport,
                "text": text,
            }
        )

    return documents


def split_into_sections(text: str) -> list[str]:
    """
    Split policy document using Markdown headings.

    Each ## heading starts a new semantic section.
    """

    sections = re.split(r"\n(?=## )", text)

    return [
        section.strip()
        for section in sections
        if section.strip()
    ]


def create_chunks(documents: list[dict]) -> list[dict]:
    """
    Create semantic chunks while preserving document metadata.
    """

    chunks = []

    for document in documents:

        sections = split_into_sections(document["text"])

        for section_number, section in enumerate(sections, start=1):

            chunks.append(
                {
                    "chunk_id": len(chunks),
                    "document_name": document["document_name"],
                    "airport": document["airport"],
                    "section_number": section_number,
                    "text": section,
                }
            )

    return chunks


if __name__ == "__main__":

    documents = load_documents()

    print(f"Documents loaded: {len(documents)}")

    for document in documents:
        print(
            f"- {document['document_name']} "
            f"({document['airport']})"
        )

    chunks = create_chunks(documents)

    print(f"\nChunks created: {len(chunks)}")

    print("\nSample chunks:")

    for chunk in chunks[:5]:

        print("\n" + "=" * 60)

        print(
            f"Chunk ID: {chunk['chunk_id']}\n"
            f"Document: {chunk['document_name']}\n"
            f"Airport: {chunk['airport']}\n"
            f"Section: {chunk['section_number']}"
        )

        print("-" * 60)

        print(chunk["text"])