# main.py
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime
from threading import Lock

from model_qwen import QwenGenerator

app = FastAPI(title="Qwen 0.5B Text API", version="1.1.0")

# -----------------------------
# In‑memory store (demo purpose)
# -----------------------------
class _Store:
    def __init__(self) -> None:
        self.sessions: Dict[str, str] = {}                 # session_id -> username
        self.command_queues: Dict[str, List[dict]] = {}    # session_id -> list[Command dict]
        self.prompts: Dict[str, str] = {}                  # command_id -> prompt
        self.states: Dict[str, List[dict]] = {}            # command_id -> list[state]
        self.actions: Dict[str, dict] = {}                 # command_id -> action
        self._lock = Lock()

    def with_lock(self):
        class _Ctx:
            def __init__(self, lock: Lock):
                self.lock = lock
            def __enter__(self):
                self.lock.acquire()
            def __exit__(self, exc_type, exc, tb):
                self.lock.release()
        return _Ctx(self._lock)

STORE = _Store()

# -----------------------------
# Schemas
# -----------------------------
class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="입력 프롬프트 텍스트")
    max_new_tokens: int = Field(128, ge=1, le=1024)
    temperature: float = Field(0.7, gt=0.0, le=2.0)
    top_p: float = Field(0.95, gt=0.0, le=1.0)

class GenerateResponse(BaseModel):
    text: str

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    session_id: str

class PromptRequest(BaseModel):
    session_id: str = Field(..., description="/login 으로 받은 세션")
    prompt: str = Field(..., description="실행할 명령의 자연어 프롬프트")

class PromptResponse(BaseModel):
    command_id: str
    enqueued_at: datetime

class CommandPayload(BaseModel):
    command_id: str
    prompt: str
    created_at: datetime

class StatePost(BaseModel):
    session_id: str
    command_id: str
    state: Dict[str, Any] = Field(default_factory=dict, description="현재 실행 웹의 상태")

class Ack(BaseModel):
    ok: bool = True

class ActionPayload(BaseModel):
    command_id: str
    action: Dict[str, Any]

# -----------------------------
# Utility
# -----------------------------

def _require_session(session_id: str) -> None:
    if session_id not in STORE.sessions:
        raise HTTPException(status_code=401, detail="invalid session")

# -----------------------------
# Basic text generation (kept)
# -----------------------------
@app.post("/generate", response_model=GenerateResponse)
def generate_text(req: GenerateRequest):
    try:
        generator = QwenGenerator.get()
        text = generator.generate(
            prompt=req.prompt,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )
        return GenerateResponse(text=text)
    except Exception as e:
        # 모델/메모리 오류 등 방어
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# Auth: /login
# -----------------------------
USER_CREDENTIALS = {}

@app.post("/login")
def login(body: LoginRequest):
    # 받은 학번/비번을 단순히 저장만
    USER_CREDENTIALS["username"] = body.username
    USER_CREDENTIALS["password"] = body.password
    return {"ok": True}

# -----------------------------
# Prompt Web: /prompt
# -----------------------------
@app.post("/prompt", response_model=PromptResponse)
def post_prompt(body: PromptRequest):
    _require_session(body.session_id)
    command_id = str(uuid4())
    cmd = CommandPayload(command_id=command_id, prompt=body.prompt, created_at=datetime.utcnow())
    with STORE.with_lock():
        STORE.prompts[command_id] = body.prompt
        STORE.command_queues.setdefault(body.session_id, []).append(cmd.model_dump())
    return PromptResponse(command_id=command_id, enqueued_at=cmd.created_at)

# -----------------------------
# Exec Web: /command (polling)
# -----------------------------
@app.get("/command", response_model=Optional[CommandPayload])
def get_next_command(session_id: str = Query(..., description="/login 으로 받은 세션")):
    _require_session(session_id)
    with STORE.with_lock():
        q = STORE.command_queues.get(session_id, [])
        if not q:
            return None  # FastAPI -> 200 with null or set 204 below
        cmd = q.pop(0)
    return CommandPayload(**cmd)

# -----------------------------
# Exec Web: /state
# -----------------------------
@app.post("/state", response_model=Ack)
def post_state(body: StatePost):
    _require_session(body.session_id)
    with STORE.with_lock():
        STORE.states.setdefault(body.command_id, []).append({
            "time": datetime.utcnow().isoformat(),
            "state": body.state,
        })

    # 간단 규칙: state가 들어오면 Qwen으로 액션을 생성해 /action 에서 제공
    try:
        prompt = STORE.prompts.get(body.command_id, "")
        generator = QwenGenerator.get()
        composed = (
            "You are an execution agent. Given the user's prompt and current UI state, "
            "return a single JSON action with fields {type, target, params}.\n\n"
            f"USER_PROMPT: {prompt}\nCURRENT_STATE: {body.state}\n"
            "ACTION_JSON:"
        )
        action_text = generator.generate(prompt=composed, max_new_tokens=256, temperature=0.2, top_p=0.9)
    except Exception as e:
        # 액션 생성 실패시 에러를 액션으로 래핑
        action_text = f"{{\"type\": \"error\", \"target\": null, \"params\": {{\"message\": \"{str(e)}\"}}}}"

    # 가능하면 JSON으로 파싱, 실패하면 raw 텍스트로 래핑
    action_obj: Dict[str, Any]
    try:
        import json
        parsed = json.loads(action_text)
        if isinstance(parsed, dict):
            action_obj = parsed
        else:
            action_obj = {"type": "raw", "target": None, "params": {"text": action_text}}
    except Exception:
        action_obj = {"type": "raw", "target": None, "params": {"text": action_text}}

    with STORE.with_lock():
        STORE.actions[body.command_id] = {"command_id": body.command_id, "action": action_obj}

    return Ack()

# -----------------------------
# Exec Web: /action (polling)
# -----------------------------
@app.get("/action", response_model=Optional[ActionPayload])
def get_action(command_id: str = Query(...)):
    with STORE.with_lock():
        item = STORE.actions.get(command_id)
        if not item:
            return None
    return ActionPayload(**item)

# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root():
    return {"message": "Qwen 0.5B Text API. Use /login, /prompt, /command, /state, /action"}