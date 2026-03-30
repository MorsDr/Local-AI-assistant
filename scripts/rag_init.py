import os
import psycopg2
from pgvector.psycopg2 import register_vector
import requests
import json
import re
from pathlib import Path
from utils import html_cleaner

DB_CONFIG = "postgresql://ai_archive:556445gghffg@localhost:5432/rag_base"
EMBED_MODEL = "nomic-embed-text"

script_dir=Path(__file__).resolve().parent.parent
DOCS_DIR=script_dir / "Docs"

if not DOCS_DIR.exists:
    print(f"Директория {DOCS_DIR} не найдена!")

def get_embedding(text):
    try:
        response = requests.post("http://localhost:11434/api/embeddings", json={"model": EMBED_MODEL, "prompt": text}, timeout=30)

        response.raise_for_status()
        data = response.json()

        if "embedding" not in data:
            raise ValueError("No embedding in response")

        return data["embedding"]

    except Exception as e:
        print(f"Ошибка embedding: {e}")
        return None


def sentences_split(text):
    sentences=re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text, chunk_size=1990, overlap=2):
    sentences=sentences_split(text)
    chunks=[]
    current_chunk=[]
    current_length=0
    for sentence in sentences:
        if current_length+len(sentence)<=chunk_size:
            current_chunk.append(sentence)
            current_length+=len(sentence)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk=current_chunk[-overlap:]
            current_chunk.append(sentence)
            current_length=sum(len(s) for s in current_chunk)
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks


def process_files():
    conn = None

    try:
        conn = psycopg2.connect(DB_CONFIG)
        register_vector(conn)
        cur = conn.cursor()

        for filename in os.listdir(DOCS_DIR):
            if filename.endswith((".md",".txt")):
                continue

            path = os.path.join(DOCS_DIR, filename)

            cur.execute("SELECT EXISTS(SELECT 1 FROM rag_storage WHERE metadata->>'file'=%s)",(filename,))

            if cur.fetchone()[0] > 0:
                print(f"Пропуск {filename} (уже есть)")
                continue

            print(f"Обработка {filename}...")


            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            if filename.endswith(".html"):
                text=html_cleaner(text)

            chunks = chunk_text(text)

            for chunk in chunks:
                print(f"Чанк длинной {len(chunk)}")
                embedding = get_embedding(chunk)

                if embedding is None:
                    continue

                cur.execute("""INSERT INTO rag_storage (content, embedding, metadata) VALUES (%s, %s, %s)""",(chunk, embedding, json.dumps({"file": filename})))

            conn.commit()  # коммит после каждого файла

        cur.close()

    except Exception as e:
        print(f"Ошибка: {e}")
        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    process_files()
