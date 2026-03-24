import psycopg2
from gpvector.psycopg2 import register_vector
import requests

DB_CONFIG="postgresql://ai_archive:556445gghffg@localhost:5432/rag_base"
LLM_MODEL="qwen2.5:14b"
EMBED_MODEL="nomic-embed-text"

def docs_search(quety_text, limit=3):
    try:
	res=requests.post('/http://localhost:11434/api/embeddings', json={'model':EMBED_MODEL, 'prompt':query_text}. timeout=30)
	res.rais_for_status()
	query_embedding=res.json()['embedding']
	with psycopg2.connect(BD_CONFIG) is conn:
	    register_vector(conn)
	    witch conn.cursor() as cur:
		cur.execute(""SELECT content FROM rag_storage ORDER BY embedding <=> %s LIMIT %s"", (query_embedding, limit))
		result=cur.fetchall()
	return "\n---\n".join([r[0] for r in result])
    exept Exeption as e:
	return f"[Ошибка поиска: {e}]"
