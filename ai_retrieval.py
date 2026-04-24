from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import re


TOKEN_RE = re.compile(r"[a-z0-9]+")
FRONTMATTER_BOUNDARY = "---"
MAX_CHUNKS_PER_DOC = 2
METADATA_SCORE_WEIGHTS = {
    "species": 1.2,
    "life_stage": 1.0,
    "topics": 0.8,
    "care_type": 0.6,
}


@dataclass
class RetrievedPassage:
    doc_id: str
    title: str
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, tuple[str, ...]] = field(default_factory=dict)


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
            metadata_boost = self._score_metadata_match(query_tokens, chunk.metadata)
            if overlap == 0 and keyword_hits == 0 and metadata_boost == 0:
                continue
            ranked.append(
                RetrievedPassage(
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=round(overlap * 1.0 + keyword_hits * 0.15 + metadata_boost, 2),
                    metadata=chunk.metadata,
                )
            )

        if not ranked:
            return self._chunks[:top_k]

        ranked.sort(key=lambda item: item.score, reverse=True)
        return self._select_diverse_top_chunks(ranked, top_k=top_k)

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

            metadata, body = self._split_frontmatter(raw_text)
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
            if not paragraphs:
                continue
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
                        metadata=metadata,
                    )
                )

    def _extract_title(self, first_paragraph: str, fallback: str) -> str:
        if first_paragraph.startswith("#"):
            return first_paragraph.lstrip("# ").strip()
        return fallback.replace("_", " ").title()

    def _split_frontmatter(self, raw_text: str) -> tuple[dict[str, tuple[str, ...]], str]:
        if not raw_text.startswith(f"{FRONTMATTER_BOUNDARY}\n"):
            return {}, raw_text

        lines = raw_text.splitlines()
        boundary_index = None
        for index in range(1, len(lines)):
            if lines[index].strip() == FRONTMATTER_BOUNDARY:
                boundary_index = index
                break

        if boundary_index is None:
            return {}, raw_text

        metadata = self._parse_metadata_lines(lines[1:boundary_index])
        body = "\n".join(lines[boundary_index + 1:]).strip()
        return metadata, body

    def _parse_metadata_lines(self, lines: List[str]) -> dict[str, tuple[str, ...]]:
        metadata: dict[str, tuple[str, ...]] = {}
        for raw_line in lines:
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip().lower().replace("-", "_")
            cleaned_value = value.strip().strip("[]")
            if not normalized_key or not cleaned_value:
                continue
            parts = tuple(
                item.strip()
                for item in cleaned_value.split(",")
                if item.strip()
            )
            if parts:
                metadata[normalized_key] = parts
        return metadata

    def _score_metadata_match(self, query_tokens: set[str], metadata: dict[str, tuple[str, ...]]) -> float:
        score = 0.0
        for key, values in metadata.items():
            weight = METADATA_SCORE_WEIGHTS.get(key, 0.5)
            metadata_tokens: set[str] = set()
            for value in values:
                metadata_tokens.update(self._tokenize(value))
            if not metadata_tokens:
                continue
            score += len(query_tokens & metadata_tokens) * weight
        return score

    def _select_diverse_top_chunks(self, ranked: List[RetrievedPassage], top_k: int) -> List[RetrievedPassage]:
        selected: List[RetrievedPassage] = []
        overflow: List[RetrievedPassage] = []
        doc_counts: dict[str, int] = {}

        for chunk in ranked:
            current_count = doc_counts.get(chunk.doc_id, 0)
            if current_count >= MAX_CHUNKS_PER_DOC:
                overflow.append(chunk)
                continue
            selected.append(chunk)
            doc_counts[chunk.doc_id] = current_count + 1
            if len(selected) == top_k:
                return selected

        for chunk in overflow:
            selected.append(chunk)
            if len(selected) == top_k:
                break

        return selected

    def _tokenize(self, text: str) -> set[str]:
        return set(TOKEN_RE.findall(text.lower()))
