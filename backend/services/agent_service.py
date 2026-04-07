"""
Agent Service
=============
Wraps the Anthropic API with:
  - RAG context injection (Qdrant search before every call)
  - Live sensor context (latest readings injected into system prompt)
  - Streaming token-by-token via async generator
  - Synchronous (non-streaming) variant for the HTTP endpoint

Designed to be extended into a full LangGraph multi-agent system.
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from core.config import get_settings
from services.sensor_service import SensorService

logger   = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an AI Operations Co-pilot for an industrial energy plant.
You have access to real-time sensor data, maintenance logs, and technical documentation.

Your role:
- Detect and explain equipment anomalies from sensor data
- Answer questions about maintenance procedures and failure patterns
- Recommend corrective actions with urgency scores (LOW / MEDIUM / HIGH / CRITICAL)
- Cite your sources when answering from documentation

Rules:
- Be concise and technical. Operators are experienced engineers.
- Always state units (°C, mm/s, bar, RPM, MW) when quoting sensor values.
- If RUL (remaining useful life) data is available, always mention it.
- If you're uncertain, say so — never guess on safety-critical matters.
- Format recommendations as numbered lists when there are multiple steps.
"""


class AgentService:

    def __init__(self):
        self._api_key    = settings.ANTHROPIC_API_KEY
        self._model      = settings.CLAUDE_MODEL
        self._rag_client = self._init_rag()

    def _init_rag(self):
        """Lazy-init Qdrant client. Returns None if Qdrant not available."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=5,
            )
            client.get_collections()   # ping
            self._Filter    = Filter
            self._FieldCond = FieldCondition
            self._MatchVal  = MatchValue
            logger.info("Agent: Qdrant connected.")
            return client
        except Exception as e:
            logger.warning("Agent: Qdrant unavailable (%s) — RAG disabled.", e)
            return None

    # ── RAG retrieval ─────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, "_embed_model"):
            self._embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._embed_model.encode([text]).tolist()[0]

    def _rag_search(
        self,
        query: str,
        asset_type: Optional[str] = None,
        limit: int = 4,
    ) -> list[dict]:
        if not self._rag_client:
            return []
        try:
            conditions = []
            if asset_type:
                conditions.append(
                    self._FieldCond(key="asset_type",
                                    match=self._MatchVal(value=asset_type))
                )
            flt  = self._Filter(must=conditions) if conditions else None
            hits = self._rag_client.search(
                collection_name="energy_docs",
                query_vector=self._embed(query),
                query_filter=flt,
                limit=limit,
                score_threshold=0.30,
                with_payload=True,
            )
            return [
                {
                    "score":    round(h.score, 3),
                    "title":    h.payload.get("title", ""),
                    "section":  h.payload.get("section", ""),
                    "category": h.payload.get("category", ""),
                    "text":     h.payload.get("text", "")[:500],
                }
                for h in hits
            ]
        except Exception as e:
            logger.warning("RAG search failed: %s", e)
            return []

    # ── Context builders ──────────────────────────────────────────────────────

    def _build_sensor_context(self, asset_id: Optional[str]) -> str:
        if not asset_id:
            return ""
        try:
            readings = SensorService.get_latest(asset_id)
            if not readings:
                return ""
            lines = [f"## Live sensor data — {asset_id}"]
            for r in readings:
                val   = f"{r['value']:.3f} {r['unit']}" if r["value"] is not None else "N/A"
                alert = r["alert_level"]
                flag  = " ⚠" if alert == "WARNING" else " 🔴" if alert == "CRITICAL" else ""
                rul   = f" | RUL: {r['rul_hours']:.0f}h" if r.get("rul_hours") else ""
                lines.append(f"  {r['sensor']:25s}: {val:15s} [{alert}]{flag}{rul}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Could not fetch sensor context: %s", e)
            return ""

    @staticmethod
    def _build_rag_context(hits: list[dict]) -> str:
        if not hits:
            return ""
        parts = ["## Relevant documentation"]
        for i, h in enumerate(hits, 1):
            parts.append(
                f"\n[Source {i}] {h['title']} — {h['section']}\n"
                f"(relevance: {h['score']:.2f})\n{h['text']}"
            )
        return "\n".join(parts)

    def _build_messages(
        self,
        message: str,
        asset_id: Optional[str],
        history: list[dict],
        rag_hits: list[dict],
    ) -> list[dict]:
        sensor_ctx = self._build_sensor_context(asset_id)
        rag_ctx    = self._build_rag_context(rag_hits)

        context_block = "\n\n".join(filter(None, [sensor_ctx, rag_ctx]))
        if context_block:
            user_content = f"{context_block}\n\n---\n\nUser question: {message}"
        else:
            user_content = message

        messages = []
        # Inject conversation history (last 10 turns to stay within context)
        for turn in history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_content})
        return messages

    # ── Streaming response ────────────────────────────────────────────────────

    async def stream_response(
        self,
        session_id: str,
        message: str,
        asset_id: Optional[str] = None,
        history: list[dict] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Yields WS message dicts:
          { type: "agent_chunk", session_id, delta }
          { type: "agent_done",  session_id, sources }
          { type: "agent_error", session_id, detail }
        """
        history  = history or []
        asset_type = None
        if asset_id:
            if "TRB" in asset_id:   asset_type = "turbine"
            elif "CMP" in asset_id: asset_type = "compressor"
            elif "PMP" in asset_id: asset_type = "pump"

        rag_hits = self._rag_search(message, asset_type=asset_type)
        messages = self._build_messages(message, asset_id, history, rag_hits)

        if not self._api_key:
            # Dev mode: echo back context without calling the API
            yield {"type": "agent_chunk", "session_id": session_id,
                   "delta": "[API key not set — dev mode]\n\n"}
            if rag_hits:
                yield {"type": "agent_chunk", "session_id": session_id,
                       "delta": f"Found {len(rag_hits)} RAG sources.\n"}
            yield {"type": "agent_done", "session_id": session_id,
                   "sources": rag_hits}
            return

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key":         self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type":      "application/json",
                    },
                    json={
                        "model":      self._model,
                        "max_tokens": 1024,
                        "system":     SYSTEM_PROMPT,
                        "messages":   messages,
                        "stream":     True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")
                        if etype == "content_block_delta":
                            delta = event.get("delta", {}).get("text", "")
                            if delta:
                                yield {"type": "agent_chunk",
                                       "session_id": session_id,
                                       "delta": delta}
                        elif etype == "message_stop":
                            break

            yield {"type": "agent_done", "session_id": session_id,
                   "sources": rag_hits}

        except httpx.HTTPStatusError as e:
            logger.error("Anthropic API error: %s", e)
            yield {"type": "agent_error", "session_id": session_id,
                   "detail": f"API error {e.response.status_code}"}
        except Exception as e:
            logger.exception("Agent stream error")
            yield {"type": "agent_error", "session_id": session_id,
                   "detail": str(e)}

    # ── Synchronous (non-streaming) ───────────────────────────────────────────

    async def respond(
        self,
        session_id: str,
        message: str,
        asset_id: Optional[str] = None,
        history: list[dict] = None,
    ) -> dict:
        """Collects the full streamed response into one dict for the REST endpoint."""
        history  = history or []
        chunks   = []
        sources  = []

        async for event in self.stream_response(session_id, message, asset_id, history):
            if event["type"] == "agent_chunk":
                chunks.append(event["delta"])
            elif event["type"] == "agent_done":
                sources = event.get("sources", [])
            elif event["type"] == "agent_error":
                raise RuntimeError(event["detail"])

        return {
            "session_id":    session_id,
            "answer":        "".join(chunks),
            "sources":       sources,
            "model":         self._model,
            "input_tokens":  0,   # populated from usage block in production
            "output_tokens": 0,
        }
