from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import json
import asyncio
USE_MOCK_MODEL = True  # ← 테스트 목업 데이터 사용 시 True, 실제 배포 시 False 해주세용 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       
    allow_credentials=True,
    allow_methods=["*"],   # POST, GET, OPTIONS 등 모두 허용
    allow_headers=["*"],
)

# 로그인 및 상태 전역 변수
STUDENT_ID = None
PASSWORD = None
TASK_TYPE = 0
PROMPT_TEXT = None
PROMPT_EVENT = asyncio.Event()
PROMPT_EVENT.set()
LOGIN_EVENT = asyncio.Event()
LOGIN_EVENT.set()

EXECUTION_WEB_CONNECTED = False #얘는 실행 웹
LAST_POLL_TIME = None

BROWSER_RUNNING = False #얜 브라우저
BROWSER_COUNT = 0

class LoginRequest(BaseModel):
    student_id: str
    password: str

@app.post("/login")
async def login(request: LoginRequest):
    global STUDENT_ID, PASSWORD, TASK_TYPE, LOGIN_EVENT

    if not LOGIN_EVENT.is_set(): # 이미 대기 중인 로그인 요청이 있으면 거절
        raise HTTPException(status_code=409, detail="이미 대기 중인 로그인 요청이 있습니다.")

    # state.json 삭제 (값이 계속 남아있으면 로그인할 때 꼬여서 넣음)
    state_path = os.path.join(os.path.dirname(__file__), "state.json")
    if os.path.exists(state_path):
        os.remove(state_path)
        print(f"[로그인] 이전 state.json 삭제 완료")

    login_state_path = os.path.join(os.path.dirname(__file__), "login_state.json") #로그인 세션 유지 파일 생성
    login_info = {
        "logged_in": True,
        "student_id": request.student_id,
    }
    with open(login_state_path, "w", encoding="utf-8") as f:
        json.dump(login_info, f, ensure_ascii=False, indent=2)
    print("[로그인] login_state.json 생성 완료")

    STUDENT_ID = request.student_id
    PASSWORD = request.password
    TASK_TYPE = 1
    LOGIN_EVENT.clear()

    print(f"[로그인] 로그인 요청 접수: {request.student_id}")

    return {
        "ok": True,
        "student_id": STUDENT_ID,
        "message": "로그인 요청이 접수되었습니다.",
    }


@app.post("/execution_web/init") #실행웹 시작 때  백엔드의 상태(state.json, PROMPT_TEXT 등)를 초기화
async def execution_web_init(request: dict):
    global PROMPT_TEXT

    print("\n[INIT] 실행웹 초기화 요청 수신")

    PROMPT_TEXT = "" # PROMPT_TEXT 초기화

    for fname in ["state.json", "login_state.json"]: # 이전에 남아있으면 무조건 삭제 해야함.
        path = os.path.join(os.path.dirname(__file__), fname)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"[INIT] {fname} 삭제 완료")
            except Exception as e:
                print(f"[INIT] {fname} 삭제 실패: {e}")

    print("[INIT] 백엔드 상태 초기화 완료")
    return {"ok": True, "message": "백엔드 상태 초기화 완료"}

class PromptRequest(BaseModel):
    text: str

@app.post("/prompt")
async def prompt(request: PromptRequest):
    global PROMPT_TEXT, PROMPT_EVENT, TASK_TYPE
    
    if not PROMPT_EVENT.is_set(): # 이미 대기 중인 프롬프트가 있으면 거절
        raise HTTPException(status_code=409, detail="이미 대기 중인 프롬프트가 있습니다.")

    PROMPT_TEXT = request.text # 요기가 프롬프트 저장
    TASK_TYPE = 2
    PROMPT_EVENT.clear()

    try:
        await asyncio.wait_for(PROMPT_EVENT.wait(), timeout=30.0) # /command가 프롬프트를 가져갈 때까지 대기
    except asyncio.TimeoutError:# 타임아웃 시 상태 초기화
        PROMPT_TEXT = None
        PROMPT_EVENT.set()
        raise HTTPException(status_code=504, detail="action이 완료되지 않아 타임아웃되었습니다.")

    return {
        "ok": True,
        "prompt_text": request.text,
        "message": "프롬프트가 command로 전달되었습니다."
    }

class StateData(BaseModel):
    data: dict

@app.post("/state")
async def save_state(request: StateData):
    global PROMPT_TEXT

    
    state_data_to_save = request.data.copy() # state.json에 저장할 데이터 준비

    if PROMPT_TEXT:
        print(f"[State] 프롬프트 감지: {PROMPT_TEXT}")
        print(f"[State] 현재 UI 상태 수신됨")

        has_ui_state = "ui_state" in request.data # UI 상태 확인
        if has_ui_state:
            print(f"[State] UI 상태 URL: {request.data['ui_state'].get('url', 'N/A')}")
        else:
            print(f"[State] 경고: UI 상태 없음")

        try:# ========== 액션 생성 ==========
            if USE_MOCK_MODEL:# Mock 모드인데, 이거 나중에 지우고 그냥 아래 action_model_만 쓰면돼.
                print(f"[State] Mock 모델 사용 (테스트 모드)")
                import mock_action_model as action_model_2
            else:
                print(f"[State] 실제 모델 사용")
                import action_model_2

            observations = None
            if "ui_state" in request.data:
                ui_state = request.data["ui_state"]
                observations = {
                    "current_url": ui_state.get("url"),
                    "sidebar": ui_state.get("sidebar", [])
                }
                print(f"[State] Observations: {observations}")

            # 다음 액션 생성
            action_result = action_model_2.get_next_action(
                observations=observations,
                max_new_tokens=256
            )

            if "error" in action_result:
                raise Exception(action_result["error"])

            generated_action = action_result.get("generated_action", {})
            state_data_to_save["generated_action"] = generated_action

            status = generated_action.get("status")
            current_step = generated_action.get("current_step", 1)
            total_steps = generated_action.get("total_steps", 1)

            print(f"[State] 액션 생성 완료 (status: {status}, step: {current_step}/{total_steps})")

        except Exception as e:
            print(f"[State] 오류 발생: {e}")
            import traceback
            traceback.print_exc()

            # 폴백: 하드코딩된 trajectory
            print(f"[State] 폴백: 하드코딩된 trajectory 사용")
            temp_action = {
                "type": "trajectory",
                "actions_file": "trajectory_student_check.json",
                "description": "학적부 열람 (폴백)"
            }
            state_data_to_save["generated_action"] = temp_action

    # state.json 저장
    save_path = os.path.join(os.path.dirname(__file__), "state.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(state_data_to_save, f, ensure_ascii=False, indent=2)

    print(f"[State] state.json 저장 완료")

    return {
        "ok": True,
        "message": "state.json 저장 완료",
        "path": save_path
    }


from fastapi.responses import JSONResponse

@app.get("/command")
async def command(browser_running: str = "false", browser_count: int = 0):
    global PROMPT_TEXT, PROMPT_EVENT, TASK_TYPE, LOGIN_EVENT, STUDENT_ID, PASSWORD, EXECUTION_WEB_CONNECTED, LAST_POLL_TIME, BROWSER_RUNNING, BROWSER_COUNT
    import datetime

    # 실행 웹이 폴링하면 연결 상태 업데이트
    EXECUTION_WEB_CONNECTED = True
    LAST_POLL_TIME = datetime.datetime.now()

    # 브라우저 상태 업데이트
    BROWSER_RUNNING = browser_running.lower() == "true"
    BROWSER_COUNT = browser_count

    # If no pending task
    if TASK_TYPE == 0:
        return {
            "has_task": False,
            "message": "대기 중인 테스크가 없습니다."
        }
    current_type = TASK_TYPE
    resp = {
        "has_task": True,
        "task_type": current_type,
    }

    if current_type == 1:
        resp["type"] = "login"
        resp["student_id"] = STUDENT_ID
        resp["password"] = PASSWORD
        LOGIN_EVENT.set()
        TASK_TYPE = 0

    elif current_type == 2:
        resp["type"] = "state"
        resp["prompt_text"] = PROMPT_TEXT # TASK_TYPE을 3으로 변경 (다음은 액션 명령)
        TASK_TYPE = 3

    elif current_type == 3:
        resp["type"] = "action"

    elif current_type == 4:
        # shutdown task
        resp["type"] = "shutdown"
        # 종료 명령은 한 번만 전달하고 리셋
        TASK_TYPE = 0

    elif TASK_TYPE == 99:
        TASK_TYPE = 0
        print("[Command] TASK_TYPE=99 → 실행웹에 shutdown 명령 전달")
        return {"has_task": True, "type": "shutdown"}

    return resp

@app.get("/action")
def get_action():
    global TASK_TYPE, PROMPT_EVENT
    state_path = os.path.join(os.path.dirname(__file__), "state.json")
    if not os.path.exists(state_path):
        raise HTTPException(status_code=404, detail="state.json 파일이 존재하지 않습니다.")
    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    generated_action = data.get("generated_action", {})
    action = generated_action.get("action", {})

    # 마지막 액션 여부: action 내부의 status 필드 확인
    action_status = action.get("status")
    is_last_action = (action_status == "FINISH")

    if is_last_action:
        print(f"[Action] 마지막 액션 전달 (status: FINISH), 작업 완료")
        TASK_TYPE = 0
        PROMPT_EVENT.set()
    else:# 중간 액션 → 다시 state 요청
        print(f"[Action] 중간 액션 전달, TASK_TYPE=2로 변경 (다음 액션 생성 위해 state 요청)")
        TASK_TYPE = 2  # 다음 폴링에서 "state" 반환하여 실행 웹이 UI 상태 전송

    return JSONResponse(content=data)

@app.get("/status")
def get_status():
    """
    프론트엔드(App.jsx)에서 주기적으로 호출하는 상태 확인 엔드포인트.
    - login_state.json: 로그인 세션 유지 여부 판단
    - state.json: 현재 작업 상태 판단
    """
    base_dir = os.path.dirname(__file__)
    state_path = os.path.join(base_dir, "state.json")
    login_path = os.path.join(base_dir, "login_state.json")

    if not os.path.exists(login_path):  #로그인 세션 없음 → 로그인 해제 처리
        print("[Status] 로그인 세션 없음 → 로그인 화면으로 복귀")
        return {
            "status": "waiting",
            "message": "로그인 세션이 없습니다. 다시 로그인하세요.",
            "data": {"loginSuccess": False},
        }
    
    if not os.path.exists(state_path): #로그인 세션 존재하지만 state.json 없음 → idle (로그인 유지)
        print("[Status] 로그인됨 + 작업 없음 → idle 상태 유지")
        with open(login_path, "r", encoding="utf-8") as f:
            login_info = json.load(f)
        return {
            "status": "idle",
            "message": "현재 실행할 작업이 없습니다.",
            "data": {
                "loginSuccess": True,
                "student_id": login_info["student_id"],
            },
        }

    try:  # state.json 존재 → 작업 상태 반환
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "action_success" in data:
            try:
                os.remove(state_path)
                print("[Status] 실행 완료 감지 → state.json 삭제")
            except Exception as e:
                print(f"[Status] state.json 삭제 실패: {e}")
            return {"status": "completed", "data": data}

        print("[Status] 실행 중 → state.json 유지")
        return {"status": "processing", "data": data}

    except Exception as e:
        print(f"[Status] 상태 파일 읽기 오류: {e}")
        return {
            "status": "error",
            "message": f"state.json 읽기 중 오류: {str(e)}",
            "data": {"loginSuccess": True},
        }

@app.post("/execution_web/shutdown")
async def execution_web_shutdown(request: dict):
    """실행 웹 종료 신호 수신"""
    global EXECUTION_WEB_CONNECTED, BROWSER_RUNNING, BROWSER_COUNT, TASK_TYPE
    EXECUTION_WEB_CONNECTED = False
    BROWSER_RUNNING = False
    BROWSER_COUNT = 0
    TASK_TYPE = 4  # 종료 명령 타입
    print("[백엔드] 실행 웹 종료 신호 수신")
    return {"ok": True, "message": "실행 웹 종료 신호 수신됨"}


@app.post("/logout") #세션 브라우저랑 상태 초기화 하는 거 
async def logout():
    global STUDENT_ID, PASSWORD, PROMPT_TEXT, LOGIN_EVENT, PROMPT_EVENT, TASK_TYPE

    STUDENT_ID = None
    PASSWORD = None
    PROMPT_TEXT = None
    LOGIN_EVENT.set()
    PROMPT_EVENT.set()

    TASK_TYPE = 99  # 브라우저 종료하는 거 
    
    base_dir = os.path.dirname(__file__) # 세션 및 상태 파일 삭제
    for fname in ["login_state.json", "state.json"]:
        path = os.path.join(base_dir, fname)
        if os.path.exists(path):
            os.remove(path)
            print(f"[로그아웃] {fname} 삭제 완료")

    print("[백엔드] 로그아웃 요청 - 상태 초기화 완료")
    return {"ok": True, "message": "로그아웃 처리됨"}

@app.post("/browser/close") #브라우저 닫기 명령인데, 이거 프롬프트웹 로그아웃 하면 같이 꺼지게 만들려고 한거니까 넣어쥬세욥 ... 
async def close_browser():
    """브라우저 닫기 명령"""
    global TASK_TYPE
    TASK_TYPE = 4  # 브라우저 닫기 명령
    print("[백엔드] 브라우저 닫기 명령 설정")
    return {"ok": True, "message": "브라우저 닫기 명령 전송"}

@app.get("/execution_web/status")
async def execution_web_status(): #실행웹 연결 상태 확인 
    global EXECUTION_WEB_CONNECTED, LAST_POLL_TIME, BROWSER_RUNNING, BROWSER_COUNT
    import datetime

    if LAST_POLL_TIME: # 마지막 폴링으로부터 8초 이상 경과하면 연결 끊김으로 간주
        elapsed = (datetime.datetime.now() - LAST_POLL_TIME).total_seconds()
        if elapsed > 8:
            EXECUTION_WEB_CONNECTED = False
            BROWSER_RUNNING = False # 연결이 끊기면 브라우저 상태도 초기화
            BROWSER_COUNT = 0

    return {
        "connected": EXECUTION_WEB_CONNECTED,
        "last_poll_time": LAST_POLL_TIME.isoformat() if LAST_POLL_TIME else None,
        "browser_running": BROWSER_RUNNING,
        "browser_count": BROWSER_COUNT
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

