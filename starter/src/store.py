"""Persistent pgvector cosine search, exact scan, metadata filters and safe replacement."""
import json
import math
from typing import Any
import psycopg
from psycopg import sql
from pgvector.psycopg import register_vector
from .models import Chunk

class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not 1 <= dimensions <= 2000:
            raise ValueError('pgvector dimensions must be 1..2000')
        self.database_url, self.dimensions = database_url, dimensions

    def _connect(self):
        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    def create_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            conn.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS day6_chunks (
                strategy text NOT NULL, chunk_id text NOT NULL,
                document_id text NOT NULL, source text NOT NULL,
                page integer NOT NULL, section text NOT NULL,
                content text NOT NULL, metadata jsonb NOT NULL,
                embedding vector({}) NOT NULL,
                PRIMARY KEY(strategy, chunk_id)
            )''').format(sql.SQL(str(self.dimensions))))
            dims = conn.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid='day6_chunks'::regclass AND attname='embedding'").fetchone()[0]
            if dims != self.dimensions:
                raise ValueError(f'Existing table has vector dimension {dims}, expected {self.dimensions}. Use a matching model or explicitly migrate table.')
            conn.execute('CREATE INDEX IF NOT EXISTS day6_chunks_strategy_section_idx ON day6_chunks(strategy, section)')

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError('Chunks and vectors length mismatch')
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError('Duplicate chunk IDs')
        if any(len(v) != self.dimensions or not all(math.isfinite(float(x)) for x in v) for v in vectors):
            raise ValueError('Invalid embedding dimensions or nonfinite vector')
        # Atomic full replacement: prevents stale chunks after source updates and duplicates on re-ingest.
        with self._connect() as conn:
            conn.execute('DELETE FROM day6_chunks WHERE strategy=%s', (strategy,))
            with conn.cursor() as cur:
                for c, v in zip(chunks, vectors):
                    cur.execute('''INSERT INTO day6_chunks
                        (strategy,chunk_id,document_id,source,page,section,content,metadata,embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (strategy,c.chunk_id,c.document_id,c.source,c.page,c.metadata.get('section',''),c.text,json.dumps(c.metadata),v))

    def count(self, strategy: str) -> int:
        with self._connect() as conn:
            return conn.execute('SELECT count(*) FROM day6_chunks WHERE strategy=%s',(strategy,)).fetchone()[0]

    
    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:

        if len(query_vector) != self.dimensions or not all(
            math.isfinite(float(x)) for x in query_vector
        ):
            raise ValueError("Invalid query vector")

        if top_k < 1 or top_k > 100:
            raise ValueError("top_k must be 1..100")

        allowed = {"section", "document_id", "source", "page"}
        filters = filters or {}

        if set(filters) - allowed:
            raise ValueError("Unsupported metadata filter")

        where = [sql.SQL("strategy = %s")]
        args = [strategy]

        for key, val in filters.items():
            where.append(
                sql.SQL("{} = %s").format(sql.Identifier(key))
            )
            args.append(val)

        stmt = sql.SQL("""
            SELECT
                chunk_id,
                document_id,
                source,
                page,
                section,
                content,
                metadata,
                1 - (embedding <=> %s::vector) AS score
            FROM day6_chunks
            WHERE {}
            ORDER BY embedding <=> %s::vector, chunk_id
            LIMIT %s
        """).format(sql.SQL(" AND ").join(where))

        with self._connect() as conn:
            rows = conn.execute(
                stmt,
                [query_vector, *args, query_vector, top_k]
            ).fetchall()

        return [
            {
                "chunk_id": r[0],
                "document_id": r[1],
                "source": r[2],
                "page": r[3],
                "section": r[4],
                "text": r[5],
                "metadata": r[6],
                "score": float(r[7])
            }
            for r in rows
        ]

