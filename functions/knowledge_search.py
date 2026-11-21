"""
title: Aurai Knowledge Search
author: Aurai Platform
version: 0.1.0
description: Lets the assistant search permitted company knowledge through the Aurai knowledge service and cite the sources. PENDING - the service is delivered by aurai-knowledge-rag; until its URL is configured this tool tells the assistant that knowledge search is unavailable.
requirements: httpx
"""

from typing import Any

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        knowledge_service_url: str = Field(
            default="",
            description="Base URL of the knowledge service. Empty means not deployed yet.",
        )
        top_k: int = Field(default=5, ge=1, le=20)
        timeout_seconds: float = Field(default=15.0, gt=0)

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.valves = self.Valves()
        self._transport = transport  # tests inject a fake service

    async def search_knowledge(
        self,
        query: str,
        collections: list[str] | None = None,
        __user__: dict | None = None,
        __oauth_token__: dict | None = None,
    ) -> str:
        """
        Search the company knowledge the signed-in user is permitted to read.
        :param query: What to look for, phrased as a question or keywords.
        :param collections: Optional collection names to limit the search.
        :return: Passages with numbered sources. Cite them as [1], [2] in the answer.
        """
        if not self.valves.knowledge_service_url:
            return "Knowledge search is not available yet. Tell the user it has not been enabled in this workspace."

        token = _access_token(__oauth_token__)
        if not token:
            return "Knowledge search needs a signed-in session. Ask the user to sign in again."

        payload: dict[str, Any] = {"query": query, "top_k": self.valves.top_k}
        if collections:
            payload["collections"] = collections

        try:
            with httpx.Client(
                base_url=self.valves.knowledge_service_url.rstrip("/"),
                timeout=self.valves.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post("/v1/search", json=payload, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            return "The knowledge service could not be reached. Tell the user and do not guess the answer."

        if response.status_code == 403:
            return "The user may not search those collections. Tell them they do not have access."
        if response.status_code != 200:
            return "The knowledge service returned an error. Tell the user and do not guess the answer."

        return format_results(response.json().get("results", []))


def _access_token(oauth_token: dict | None) -> str:
    if isinstance(oauth_token, dict):
        return str(oauth_token.get("access_token", ""))
    return ""


def format_results(results: list[dict[str, Any]]) -> str:
    """Render passages as numbered sources the model can cite."""
    if not results:
        return "No permitted sources matched. Say that nothing was found rather than answering from memory."
    lines = []
    for number, passage in enumerate(results, start=1):
        source = passage["source"]
        freshness = f", ingested {source['freshness']}" if source.get("freshness") else ""
        lines.append(
            f"[{number}] {source['title']} ({source['collection']}, {source['classification']}{freshness})\n"
            f"{passage['text']}"
        )
    return "\n\n".join(lines)
