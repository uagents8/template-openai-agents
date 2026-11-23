"""An OpenAI Agents SDK agent behind FastAPI - the uAgents8 "OpenAI Agents SDK" template.

Kept deliberately close to a small, proven shape - same agent, same tool, same pinned
dependencies - so nothing about the measured footprint changes.

  GET  /      health - the platform only checks that the port accepts connections
  POST /ask   {"question": "..."} -> {"question", "answer", "mode"}

OpenAI-only by design: the SDK itself only talks to OpenAI's own API, so unlike the LangGraph
template there is no LLM_PROVIDER switch here. With no OPENAI_API_KEY set the agent still
starts, still runs its one tool for real, and answers with that real result plus an explicit
nudge to add a key - see NO_KEY_MESSAGE below, a deliberately better first impression than
refusing to boot.

Make it yours: change the agent's instructions and tools. Delete StubModel when you no longer
want the offline mode.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from agents import Agent, Model, ModelResponse, Runner, Usage, function_tool, set_tracing_disabled
from fastapi import FastAPI
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pydantic import BaseModel, Field

AGENT_NAME = "template-openai-agents"

NO_KEY_MESSAGE = (
    "[stub: no OPENAI_API_KEY set] Your question has {tool_output}. Add OPENAI_API_KEY under "
    "Environment Variables (Sensitive on), then redeploy, for a real model instead of this stub."
)

# Traces are uploaded to a hosted dashboard by default; this template keeps everything inside your agent.
set_tracing_disabled(True)


@function_tool
def word_count(text: str) -> str:
    """Count the words and characters in a piece of text."""
    return f"{len(text.split())} words, {len(text)} characters"


class StubModel(Model):
    """Offline stand-in for a model: calls `word_count` for real, then answers with NO_KEY_MESSAGE
    filled in from that real result. Deterministic, no network - this is what runs with no
    OPENAI_API_KEY set."""

    async def get_response(self, system_instructions: Any, input: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        items = input if isinstance(input, list) else [{"role": "user", "content": input}]
        tool_output = next((i.get("output") for i in reversed(items) if i.get("type") == "function_call_output"), None)
        if tool_output is None:
            question = next((i["content"] for i in reversed(items) if i.get("role") == "user"), "")
            call = ResponseFunctionToolCall(
                type="function_call", call_id="stub-call-1", name="word_count", arguments=json.dumps({"text": question})
            )
            return ModelResponse(output=[call], usage=Usage(), response_id=None)
        answer = NO_KEY_MESSAGE.format(tool_output=tool_output)
        text = ResponseOutputText(type="output_text", text=answer, annotations=[])
        message = ResponseOutputMessage(
            id="stub-msg-1", type="message", role="assistant", status="completed", content=[text]
        )
        return ModelResponse(output=[message], usage=Usage(), response_id=None)

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("StubModel does not stream")


USE_MODEL = bool(os.environ.get("OPENAI_API_KEY"))
agent = Agent(
    name="assistant",
    instructions="Answer briefly. Use the word_count tool when asked about the length of a text.",
    tools=[word_count],
    model=os.environ.get("MODEL_NAME", "gpt-4o-mini") if USE_MODEL else StubModel(),
)

app = FastAPI(title=AGENT_NAME)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/")
def index() -> dict[str, str]:
    """A friendly status route. The platform does not call it: its check is that the port accepts connections."""
    return {"status": "ok", "agent": AGENT_NAME}


@app.post("/ask")
async def ask(body: Ask) -> dict[str, str]:
    result = await Runner.run(agent, body.question)
    return {"question": body.question, "answer": str(result.final_output), "mode": "model" if USE_MODEL else "stub"}


if __name__ == "__main__":
    # The platform sets PORT; listen on all interfaces, not just localhost.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
