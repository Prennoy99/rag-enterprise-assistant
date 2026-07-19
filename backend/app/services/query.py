import uuid
from typing import AsyncGenerator

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import DocumentChunk

# Standard RRF constant (Cormack et al.) - dampens the impact of rank 1 vs rank 2
# so one search method doesn't dominate just because it's more confident near the top.
RRF_K = 60
# How many candidates to pull from each individual search before fusion. Wider than
# top_k so RRF has enough overlap information to actually re-rank rather than just
# concatenate.
CANDIDATE_MULTIPLIER = 4

SYSTEM_PROMPT = """You are an expert document analyst assistant.
Answer questions based ONLY on the provided document context.
If the answer is not in the context, say "I couldn't find this information in the uploaded documents."
Be concise, accurate, and cite which sections support your answer.

Context:
{context}
"""


class SourcesEvent:
    """Wraps the retrieved chunks so the router can distinguish them from answer tokens in the stream."""

    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks


class QueryService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
            streaming=True,
        )

    async def query(
        self, question: str, document_ids: list[uuid.UUID] | None, db: AsyncSession
    ) -> AsyncGenerator[str | SourcesEvent, None]:
        query_vector = await self.embeddings.aembed_query(question)
        chunks = await self._hybrid_search(question, query_vector, document_ids, db)
        yield SourcesEvent(chunks)

        if not chunks:
            yield "I couldn't find relevant information in the uploaded documents."
            return

        context = "\n\n---\n\n".join(
            f"[chunk {c.chunk_index} | doc {c.document_id}]\n{c.content}"
            for c in chunks
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{question}"),
        ])
        chain = prompt | self.llm

        async for token in chain.astream({"context": context, "question": question}):
            yield token.content

    async def _hybrid_search(self, question, query_vector, document_ids, db, top_k=None):
        """Fuses vector similarity and Postgres full-text search via Reciprocal Rank Fusion.

        Vector search finds semantically related chunks even without shared words; full-text
        search reliably surfaces exact terms (names, codes, acronyms) that embeddings can blur.
        RRF combines their rankings without needing the two scores to be on comparable scales.
        """
        top_k = top_k or settings.RETRIEVER_TOP_K
        candidate_k = top_k * CANDIDATE_MULTIPLIER

        vector_ids = await self._vector_search_ids(query_vector, document_ids, db, candidate_k)
        fulltext_ids = await self._fulltext_search_ids(question, document_ids, db, candidate_k)

        scores: dict[uuid.UUID, float] = {}
        for rank, chunk_id in enumerate(vector_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, chunk_id in enumerate(fulltext_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)

        if not scores:
            return []

        ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(ranked_ids))
        )
        chunks_by_id = {c.id: c for c in chunks_result.scalars().all()}
        return [chunks_by_id[i] for i in ranked_ids if i in chunks_by_id]

    async def _vector_search_ids(self, query_vector, document_ids, db, top_k):
        vector_str = f"[{','.join(str(v) for v in query_vector)}]"
        params = {"vector": vector_str, "top_k": top_k}

        where_clause = "AND document_id IN :ids" if document_ids else ""
        sql = text(f"""
            SELECT id FROM document_chunks
            WHERE embedding IS NOT NULL
            {where_clause}
            ORDER BY embedding <=> :vector::vector
            LIMIT :top_k
        """)
        if document_ids:
            sql = sql.bindparams(bindparam("ids", expanding=True))
            params["ids"] = list(document_ids)

        result = await db.execute(sql, params)
        return [row[0] for row in result.fetchall()]

    async def _fulltext_search_ids(self, question, document_ids, db, top_k):
        params = {"query": question, "top_k": top_k}

        where_clause = "AND document_id IN :ids" if document_ids else ""
        sql = text(f"""
            SELECT id FROM document_chunks
            WHERE content_tsv @@ plainto_tsquery('english', :query)
            {where_clause}
            ORDER BY ts_rank(content_tsv, plainto_tsquery('english', :query)) DESC
            LIMIT :top_k
        """)
        if document_ids:
            sql = sql.bindparams(bindparam("ids", expanding=True))
            params["ids"] = list(document_ids)

        result = await db.execute(sql, params)
        return [row[0] for row in result.fetchall()]
