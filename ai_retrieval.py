from dataclasses import dataclass
from pathlib import Path
from typing import List
import re


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievedPassage:
    doc_id: str
    title: str
    chunk_id: str
    content: str
    score: float


class LocalKnowledgeBase:
    """Simple lexical retrieval over a curated local document set."""

    def __init__(self, knowledge_dir: Path | None = None):
        base_dir = Path(__file__).resolve().parent
        self.knowledge_dir = knowledge_dir or base_dir / "knowledge_base"
        self._chunks: List[RetrievedPassage] = []

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedPassage]:
        self._ensure_loaded()
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return self._chunks[:top_k]

        ranked: List[RetrievedPassage] = []
        for chunk in self._chunks:
            content_tokens = self._tokenize(chunk.content)
            overlap = len(query_tokens & content_tokens)
            keyword_hits = sum(chunk.content.lower().count(token) for token in query_tokens)
            if overlap == 0 and keyword_hits == 0:
                continue
            ranked.append(
                RetrievedPassage(
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=round(overlap * 1.0 + keyword_hits * 0.15, 2),
                )
            )

        if not ranked:
            return self._chunks[:top_k]

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    def list_doc_ids(self) -> List[str]:
        self._ensure_loaded()
        return sorted({chunk.doc_id for chunk in self._chunks})

    def _ensure_loaded(self) -> None:
        if self._chunks:
            return

        for path in sorted(self.knowledge_dir.glob("*.md")):
            raw_text = path.read_text(encoding="utf-8").strip()
            if not raw_text:
                continue

            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw_text) if part.strip()]
            title = self._extract_title(paragraphs[0], path.stem)
            for index, paragraph in enumerate(paragraphs, start=1):
                if len(self._tokenize(paragraph)) < 8:
                    continue
                self._chunks.append(
                    RetrievedPassage(
                        doc_id=path.stem,
                        title=title,
                        chunk_id=f"{path.stem}#{index}",
                        content=paragraph,
                        score=0.0,
                    )
                )

    def _extract_title(self, first_paragraph: str, fallback: str) -> str:
        if first_paragraph.startswith("#"):
            return first_paragraph.lstrip("# ").strip()
        return fallback.replace("_", " ").title()

    def _tokenize(self, text: str) -> set[str]:
        return set(TOKEN_RE.findall(text.lower()))
