from src.document_loader import load_documents, create_chunks


def test_documents_loaded():
    documents = load_documents()

    assert len(documents) == 7


def test_chunks_created():
    documents = load_documents()
    chunks = create_chunks(documents)

    assert len(chunks) > 0


def test_sfo_pricing_exists():
    documents = load_documents()
    chunks = create_chunks(documents)

    sfo_chunks = [
        chunk
        for chunk in chunks
        if chunk["document_name"] == "sfo_pricing.md"
    ]

    assert len(sfo_chunks) > 0


def test_airport_metadata():
    documents = load_documents()

    airports = {document["airport"] for document in documents}

    assert "SFO" in airports
    assert "LAX" in airports
    assert "JFK" in airports