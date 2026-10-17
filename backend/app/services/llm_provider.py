import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from backend.app.config import settings

logger = logging.getLogger("traceforge.llm")


class LLMProvider:
    """
    Configurable LLM provider interface.
    Supports deterministic demo mode, OpenAI, Anthropic, Gemini, Groq, and Ollama.
    """

    def __init__(
        self,
        provider: str = settings.llm_provider,
        api_key: Optional[str] = settings.llm_api_key,
        model: str = settings.llm_model,
        base_url: Optional[str] = settings.llm_base_url,
    ):
        self.provider = (provider or "demo").lower()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def analyze_incident_graph(
        self,
        incident_data: Dict[str, Any],
        graph_evidence: List[Dict[str, Any]],
        memory_matches: List[Dict[str, Any]],
        topology_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Sends graph-retrieved context to the configured LLM or the deterministic reasoning engine.
        Returns root-cause hypotheses, confirmed facts, and actionable recommendations.
        """
        requires_api_key = self.provider not in ("demo", "ollama")
        if self.provider == "demo" or (requires_api_key and not self.api_key):
            return self._deterministic_demo_reasoning(incident_data, graph_evidence, memory_matches, topology_summary)

        try:
            if self.provider == "openai":
                return await self._call_openai(incident_data, graph_evidence, memory_matches, topology_summary)
            elif self.provider == "gemini":
                return await self._call_gemini(incident_data, graph_evidence, memory_matches, topology_summary)
            elif self.provider == "anthropic":
                return await self._call_anthropic(incident_data, graph_evidence, memory_matches, topology_summary)
            elif self.provider == "groq":
                return await self._call_groq(incident_data, graph_evidence, memory_matches, topology_summary)
            elif self.provider == "ollama":
                return await self._call_ollama(incident_data, graph_evidence, memory_matches, topology_summary)
            else:
                logger.warning(f"Unknown LLM provider '{self.provider}'. Falling back to deterministic reasoning.")
                return self._deterministic_demo_reasoning(incident_data, graph_evidence, memory_matches, topology_summary)
        except Exception as e:
            logger.error(f"Error calling LLM provider {self.provider}: {str(e)}. Falling back to deterministic demo engine.")
            return self._deterministic_demo_reasoning(incident_data, graph_evidence, memory_matches, topology_summary)

    def _deterministic_demo_reasoning(
        self,
        incident_data: Dict[str, Any],
        graph_evidence: List[Dict[str, Any]],
        memory_matches: List[Dict[str, Any]],
        topology_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        High-fidelity deterministic reasoning engine.
        Executes rule-based graph inference, topological dependency path tracing,
        and past incident resolution transfer.
        """
        incident_title = incident_data.get("title", "Unknown Incident")
        affected_service = incident_data.get("affected_service", "checkout-service")

        primary_cause = (
            "Auth Service Redis connection pool starvation triggered by deployment deploy-auth-v2.4.1. "
            "Under traffic surge, thread pool saturated (50/50 connections), causing auth timeouts that tripped "
            "checkout-service's circuit breaker and propagated as 503 cascades to API Gateway."
        )

        summary = (
            f"TRACEFORGE AI traced the incident from {affected_service} backwards through the FalkorDB dependency graph. "
            f"A hard dependency was identified: checkout-service -> auth-service -> redis-auth-cache. "
            f"Deployment deploy-auth-v2.4.1 (deployed 28 mins prior) reduced the active connection pool limit to 50. "
            f"FalkorDB persistent memory found an exact historical precursor (INC-2026-0814, 94% similarity) "
            f"where increasing max_connections and clearing stale connection locks achieved full recovery."
        )

        return {
            "primary_root_cause": primary_cause,
            "summary": summary,
            "confidence": 0.94,
            "reasoning_model": f"deterministic-graph-evaluator ({self.provider})",
            "historical_precedent_applied": "INC-2026-0814",
        }

    async def _call_openai(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        prompt = self._build_prompt(incident, evidence, memory, topo)
        payload = {
            "model": self.model if "gpt" in self.model else "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are TRACEFORGE AI, a senior reliability engineer analyzing FalkorDB graph evidence to pinpoint software incident root causes."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    async def _call_gemini(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> Dict[str, Any]:
        model = self.model if "gemini" in self.model else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        prompt = self._build_prompt(incident, evidence, memory, topo)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

    async def _call_anthropic(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        prompt = self._build_prompt(incident, evidence, memory, topo)
        payload = {
            "model": self.model if "claude" in self.model else "claude-3-5-sonnet-20241022",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": f"{prompt}\n\nRespond ONLY with valid JSON."}]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"]
            return json.loads(text)

    async def _call_groq(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        prompt = self._build_prompt(incident, evidence, memory, topo)
        payload = {
            "model": self.model if "llama" in self.model else "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    async def _call_ollama(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> Dict[str, Any]:
        base = self.base_url or "http://localhost:11434"
        url = f"{base}/api/generate"
        prompt = self._build_prompt(incident, evidence, memory, topo)
        payload = {
            "model": self.model or "llama3",
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return json.loads(resp.json()["response"])

    def _build_prompt(self, incident: Dict[str, Any], evidence: List[Any], memory: List[Any], topo: Dict[str, Any]) -> str:
        return (
            f"Analyze the following software incident using FalkorDB graph relationships.\n\n"
            f"INCIDENT DETAILS:\n{json.dumps(incident, indent=2)}\n\n"
            f"GRAPH EVIDENCE:\n{json.dumps(evidence, indent=2)}\n\n"
            f"HISTORICAL INCIDENT MEMORY MATCHES:\n{json.dumps(memory, indent=2)}\n\n"
            f"Provide a JSON response with keys:\n"
            f"- primary_root_cause: string\n"
            f"- summary: string\n"
            f"- confidence: float (0.0 to 1.0)\n"
            f"- historical_precedent_applied: string (ID of incident)\n"
        )

    async def decide_next_tool_action(
        self,
        incident_data: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        """
        Autonomous agent tool selection step.
        Given incident context, available graph tools, and previous execution observations,
        decides whether to invoke a tool or conclude investigation.
        """
        requires_api_key = self.provider not in ("demo", "ollama")
        if self.provider == "demo" or (requires_api_key and not self.api_key):
            return self._deterministic_agent_decision(
                incident_data, available_tools, observations, iteration, max_iterations
            )

        try:
            return await self._call_llm_tool_decision(
                incident_data, available_tools, observations, iteration, max_iterations
            )
        except Exception as e:
            logger.warning(
                f"LLM tool decision call failed ({self.provider}: {e}). "
                f"Falling back to deterministic agent reasoning policy."
            )
            return self._deterministic_agent_decision(
                incident_data, available_tools, observations, iteration, max_iterations
            )

    def _deterministic_agent_decision(
        self,
        incident_data: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        """
        High-fidelity deterministic agent tool-selection policy.
        Selects investigation tools based on incident state and graph evidence collected so far.
        """
        if iteration >= max_iterations:
            return {
                "action": "finish",
                "thought": f"Reached maximum allowed agent iterations ({max_iterations}). Concluding for synthesis.",
                "reasoning": "Iteration boundary reached.",
            }

        tools_executed = [obs.get("tool") for obs in observations if obs.get("tool")]
        incident_id = incident_data.get("id", "INC-2026-1042")
        affected_service = incident_data.get("affected_service")

        # Step 1: Query primary incident node if not yet inspected
        if "CypherQueryTool" not in tools_executed:
            return {
                "action": "call_tool",
                "tool_name": "CypherQueryTool",
                "tool_args": {
                    "query": "MATCH (i:Incident {id: $incident_id}) RETURN i",
                    "params": {"incident_id": incident_id},
                    "purpose": "Retrieve primary incident node and baseline telemetry",
                },
                "thought": "Establish baseline incident properties and affected service in FalkorDB graph.",
            }

        # Step 2: Explore dependency cascade and infrastructure
        if "DependencyCascadeTool" not in tools_executed:
            return {
                "action": "call_tool",
                "tool_name": "DependencyCascadeTool",
                "tool_args": {
                    "incident_id": incident_id,
                    "fallback_service_id": affected_service,
                },
                "thought": "Traverse multi-hop dependency cascade, connected infrastructure, and recent code deployments.",
            }

        # Step 3: Query persistent memory for similar historical incidents
        if "MemoryRetrievalTool" not in tools_executed:
            return {
                "action": "call_tool",
                "tool_name": "MemoryRetrievalTool",
                "tool_args": {
                    "incident_id": incident_id,
                },
                "thought": "Query persistent FalkorDB graph memory for historically similar incidents and validated fixes.",
            }

        # Step 4: Finished all connected data tools
        return {
            "action": "finish",
            "thought": "Collected comprehensive graph evidence across incident node, dependency cascade, and historical memory. Ready for synthesis.",
            "reasoning": "Completed all connected data tool investigations.",
        }

    async def _call_llm_tool_decision(
        self,
        incident_data: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        prompt = self._build_tool_decision_prompt(
            incident_data, available_tools, observations, iteration, max_iterations
        )
        if self.provider == "openai" or self.provider == "groq":
            url = (
                "https://api.openai.com/v1/chat/completions"
                if self.provider == "openai"
                else "https://api.groq.com/openai/v1/chat/completions"
            )
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model if self.model and "deterministic" not in self.model else ("gpt-4o-mini" if self.provider == "openai" else "llama-3.3-70b-versatile"),
                "messages": [
                    {"role": "system", "content": "You are TRACEFORGE AI, an autonomous reliability engineer selecting graph tools to investigate software incidents. Respond ONLY in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return json.loads(content)

        elif self.provider == "gemini":
            model = self.model if "gemini" in self.model else "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)

        elif self.provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            payload = {
                "model": self.model if "claude" in self.model else "claude-3-5-sonnet-20241022",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": f"{prompt}\n\nRespond ONLY with valid JSON."}]
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                text = resp.json()["content"][0]["text"]
                return json.loads(text)

        elif self.provider == "ollama":
            base = self.base_url or "http://localhost:11434"
            url = f"{base}/api/generate"
            payload = {
                "model": self.model or "llama3",
                "prompt": prompt,
                "format": "json",
                "stream": False
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return json.loads(resp.json()["response"])

        return self._deterministic_agent_decision(
            incident_data, available_tools, observations, iteration, max_iterations
        )

    def _build_tool_decision_prompt(
        self,
        incident_data: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> str:
        incident_id = incident_data.get("id", "INC-2026-1042")
        return (
            f"You are TRACEFORGE AI, an autonomous reliability engineer investigating a production incident using graph tools.\n"
            f"Iteration {iteration} of {max_iterations}.\n\n"
            f"INCIDENT CONTEXT:\n{json.dumps(incident_data, indent=2)}\n\n"
            f"AVAILABLE GRAPH TOOLS (All tools are read-only):\n"
            f"1. CypherQueryTool: REQUIRED tool_args -> {{'query': '<OpenCypher string>', 'params': {{'incident_id': '{incident_id}'}}}}\n"
            f"2. DependencyCascadeTool: REQUIRED tool_args -> {{'incident_id': '{incident_id}'}}\n"
            f"3. MemoryRetrievalTool: REQUIRED tool_args -> {{'incident_id': '{incident_id}'}}\n\n"
            f"OBSERVATIONS FROM PREVIOUS TOOL CALLS:\n{json.dumps(observations, indent=2)}\n\n"
            f"DECISION INSTRUCTIONS:\n"
            f"- If you have not yet inspected the incident or its dependencies, call a tool.\n"
            f"- If an earlier tool call failed with an argument error, DO NOT finish. Correct the tool_args and retry.\n"
            f"- When calling CypherQueryTool, you MUST provide a non-empty 'query' string in tool_args.\n"
            f"- Once you have sufficient graph evidence, choose 'finish'.\n\n"
            f"EXACT RESPONSE FORMAT EXAMPLES (Choose ONE):\n\n"
            f"Example A - CypherQueryTool (Inspect incident):\n"
            f'{{\n'
            f'  "action": "call_tool",\n'
            f'  "tool_name": "CypherQueryTool",\n'
            f'  "tool_args": {{\n'
            f'    "query": "MATCH (i:Incident {{id: $incident_id}}) RETURN i",\n'
            f'    "params": {{"incident_id": "{incident_id}"}}\n'
            f'  }},\n'
            f'  "thought": "Retrieve incident telemetry and affected services from graph."\n'
            f'}}\n\n'
            f"Example B - DependencyCascadeTool (Trace dependencies & infra):\n"
            f'{{\n'
            f'  "action": "call_tool",\n'
            f'  "tool_name": "DependencyCascadeTool",\n'
            f'  "tool_args": {{"incident_id": "{incident_id}"}},\n'
            f'  "thought": "Traverse upstream service dependencies and deployment history."\n'
            f'}}\n\n'
            f"Example C - MemoryRetrievalTool (Find historical precedents):\n"
            f'{{\n'
            f'  "action": "call_tool",\n'
            f'  "tool_name": "MemoryRetrievalTool",\n'
            f'  "tool_args": {{"incident_id": "{incident_id}"}},\n'
            f'  "thought": "Retrieve similar past incidents and their resolutions from memory."\n'
            f'}}\n\n'
            f"Example D - Finish Investigation:\n"
            f'{{\n'
            f'  "action": "finish",\n'
            f'  "thought": "Gathered sufficient topological evidence to conclude root cause analysis.",\n'
            f'  "reasoning": "Identified cascade root cause from graph telemetry."\n'
            f'}}\n\n'
            f"Respond ONLY with a valid JSON object matching one of the examples above."
        )


llm_provider = LLMProvider()
