import uuid
from typing import AsyncGenerator

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import DocumentChunk

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
        chunks = await self._similarity_search(query_vector, document_ids, db)
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

    async def _similarity_search(self, query_vector, document_ids, db, top_k=None):
        top_k = top_k or settings.RETRIEVER_TOP_K
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
        chunk_ids = [row[0] for row in result.fetchall()]
        if not chunk_ids:
            return []

        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        )
        return chunks_result.scalars().all()
