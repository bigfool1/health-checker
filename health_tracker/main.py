from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from health_tracker.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from health_tracker.graph.builder import build_graph
from health_tracker.graph.state import GraphState

app = FastAPI(title="Health Tracker", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

llm = ChatAnthropic(
    model=LLM_MODEL,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    temperature=0,
)

graph = build_graph(llm)

# in-memory session store for cross-turn slot-filling
sessions: dict[str, dict] = {}


def _get_session(cid: str) -> dict:
    if cid not in sessions:
        sessions[cid] = {}
    return sessions[cid]


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    action: str | None = None
    type: str | None = None


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session = _get_session(req.conversation_id)
    pending = session.get("pending_entities", {})
    last_response = session.get("last_response", "")

    context = ""
    if pending:
        pending_type = session.get("pending_type", "")
        missing = session.get("missing_fields", [])
        context = (
            f"上一轮对话中，用户正在记录{pending_type}，"
            f"但还缺少以下信息：{', '.join(missing)}。"
            f"系统追问了：「{last_response}」"
            f"当前用户输入可能是对这些缺失信息的补充，请据此提取 entities。"
        )

    state: GraphState = {
        "user_input": req.message,
        "context": context,
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": pending,
        "missing_fields": [],
        "response": "",
    }

    result = await graph.ainvoke(state)

    # persist pending state for next turn
    if result.get("pending_entities"):
        session["pending_entities"] = result["pending_entities"]
        session["pending_type"] = result.get("type", "")
        session["missing_fields"] = result.get("missing_fields", [])
        session["last_response"] = result.get("response", "")
    else:
        session.pop("pending_entities", None)
        session.pop("pending_type", None)
        session.pop("missing_fields", None)
        session.pop("last_response", None)

    return ChatResponse(
        response=result.get("response", ""),
        action=result.get("action"),
        type=result.get("type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("health_tracker.main:app", host="0.0.0.0", port=8000, reload=True)
