import chromadb
from chromadb.config import Settings
import os
from app import config

# Custom local embedding function to avoid background model downloads (e.g. HuggingFace)
class HashingEmbeddingFunction(chromadb.EmbeddingFunction):
    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        embeddings = []
        for text in input:
            vector = [0.0] * 128
            words = text.lower().split()
            for w in words:
                idx = hash(w) % 128
                vector[idx] += 1.0
            norm = sum(x**2 for x in vector)**0.5
            if norm > 0:
                vector = [x / norm for x in vector]
            embeddings.append(vector)
        return embeddings

# Initialize Chroma Client
try:
    if config.DB_DIR:
        os.makedirs(config.DB_DIR, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=config.DB_DIR)
    else:
        chroma_client = chromadb.EphemeralClient()
except Exception as e:
    print(f"ChromaDB Client initialization failed: {e}. Falling back to in-memory.")
    chroma_client = chromadb.EphemeralClient()

# Get or create collection using custom local embedding function
collection = chroma_client.get_or_create_collection(
    name="coding_rules",
    embedding_function=HashingEmbeddingFunction()
)

def add_standard_rules():
    """
    Seeds the VectorDB with some default coding standards if empty.
    """
    if collection.count() > 0:
        return

    default_rules = [
        {
            "id": "rule_naming_conventions",
            "document": "Functions and variable names in Python should follow snake_case. Classes must follow PascalCase. Constants must be in UPPER_CASE.",
            "metadata": {"category": "style", "language": "python"}
        },
        {
            "id": "rule_error_handling",
            "document": "Do not use bare 'except:'. Always catch specific exceptions (e.g. ValueError, KeyError) and log or re-raise them.",
            "metadata": {"category": "reliability", "language": "python"}
        },
        {
            "id": "rule_sql_injection",
            "document": "Never format or concatenate raw SQL queries using input variables. Always use parameterized queries or an ORM to prevent SQL injection.",
            "metadata": {"category": "security", "language": "database"}
        },
        {
            "id": "rule_docstrings",
            "document": "Every public module, class, and function must have a clear docstring explaining its purpose, parameters, and return types.",
            "metadata": {"category": "documentation", "language": "general"}
        },
        {
            "id": "rule_unit_tests",
            "document": "All new modules must have matching unit test cases covering positive, negative, and edge cases. Aim for at least 80% code coverage.",
            "metadata": {"category": "testing", "language": "general"}
        }
    ]

    ids = [r["id"] for r in default_rules]
    documents = [r["document"] for r in default_rules]
    metadatas = [r["metadata"] for r in default_rules]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    print(f"VectorDB initialized. Added {len(ids)} default coding standard rules.")


def query_relevant_rules(query_text: str, limit: int = 2) -> list:
    """
    Queries ChromaDB vector store for standard rules matching the code context.
    """
    # Seed database if it's empty
    if collection.count() == 0:
        add_standard_rules()

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=limit
        )
        
        # Flatten documents from results
        matched_rules = []
        if results and "documents" in results and results["documents"]:
            for doc_list in results["documents"]:
                matched_rules.extend(doc_list)
        return matched_rules
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        return []
