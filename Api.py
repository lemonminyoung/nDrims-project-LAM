from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import json
import asyncio

# ========== Mock 모드 설정 ==========
# True: Mock 데이터 사용 (모델 없이 테스트)
# False: 실제 action_model_2 사용
USE_MOCK_MODEL = True  # ← 테스트 시 True, 실제 배포 시 False
# ====================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # 또는 ["http://localhost:5173"] 처럼 제한 가능
    allow_credentials=True,
    allow_methods=["*"],            # POST, GET, OPTIONS 등 모두 허용
    allow_headers=["*"],
)

# 로그인 및 상태 전역 변수
STUDENT_ID = None
PASSWORD = None
TASK_TYPE = 0
PROMPT_TEXT = None
PROMPT_EVENT = asyncio.Event()
PROMPT_EVENT.set()  # no pending prompt initially
LOGIN_EVENT = asyncio.Event()
LOGIN_EVENT.set()   # no pending login initially

# 실행 웹 연결 상태
EXECUTION_WEB_CONNECTED = False
LAST_POLL_TIME = None

# 브라우저 상태
BROWSER_RUNNING = False
BROWSER_COUNT = 0

# 로그인 요청 모델
class LoginRequest(BaseModel):
    student_id: str
    password: str

@app.post("/login")
async def login(request: LoginRequest):
    global STUDENT_ID, PASSWORD, TASK_TYPE, LOGIN_EVENT

    # 이미 대기 중인 로그인 요청이 있으면 거절
    if not LOGIN_EVENT.is_set():
        raise HTTPException(status_code=409, detail="이미 대기 중인 로그인 요청이 있습니다.")

    # state.json 삭제 (이전 작업 결과 제거)
    state_path = os.path.join(os.path.dirname(__file__), "state.json")
    if os.path.exists(state_path):
        os.remove(state_path)
        print(f"[로그인] 이전 state.json 삭제 완료")

    #로그인 세션 유지 파일 생성
    login_state_path = os.path.join(os.path.dirname(__file__), "login_state.json")
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

    # 즉시 응답 반환 (대기하지 않음)
    print(f"[로그인] 로그인 요청 접수: {request.student_id}")

    return {
        "ok": True,
        "student_id": STUDENT_ID,
        "message": "로그인 요청이 접수되었습니다.",
    }


@app.post("/execution_web/init")
async def execution_web_init(request: dict):
    """
    실행웹이 시작될 때 호출되는 초기화 엔드포인트.
    백엔드의 상태(state.json, PROMPT_TEXT 등)를 초기화함.
    """
    global PROMPT_TEXT

    print("\n[INIT] 실행웹 초기화 요청 수신")

    # PROMPT_TEXT 초기화
    PROMPT_TEXT = ""

    # 불필요한 상태 파일 삭제
    for fname in ["state.json", "login_state.json"]:
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

    # 이미 대기 중인 프롬프트가 있으면 거절
    if not PROMPT_EVENT.is_set():
        raise HTTPException(status_code=409, detail="이미 대기 중인 프롬프트가 있습니다.")

    # 새 프롬프트 저장
    PROMPT_TEXT = request.text
    TASK_TYPE = 2
    PROMPT_EVENT.clear()

    # /command가 프롬프트를 가져갈 때까지 대기 (타임아웃 포함)
    try:
        await asyncio.wait_for(PROMPT_EVENT.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        # 타임아웃 시 상태 초기화
        PROMPT_TEXT = None
        PROMPT_EVENT.set()
        raise HTTPException(status_code=504, detail="action이 완료되지 않아 타임아웃되었습니다.")

    # /command에서 프롬프트를 가져간 것이 확인된 후 성공 응답
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

    # state.json에 저장할 데이터 준비
    state_data_to_save = request.data.copy()

    # 프롬프트가 있으면 액션 생성
    if PROMPT_TEXT:
        print(f"[State] 프롬프트 감지: {PROMPT_TEXT}")
        print(f"[State] 현재 UI 상태 수신됨")

        # UI 상태 확인
        has_ui_state = "ui_state" in request.data
        if has_ui_state:
            print(f"[State] UI 상태 URL: {request.data['ui_state'].get('url', 'N/A')}")
        else:
            print(f"[State] 경고: UI 상태 없음")

        # ========== 액션 생성 ==========
        try:
            # Mock 모드 또는 실제 모델 선택
            if USE_MOCK_MODEL:
                print(f"[State] Mock 모델 사용 (테스트 모드)")
                import mock_action_model as action_model_2
            else:
                print(f"[State] 실제 모델 사용")
                import action_model_2

            # observations 구성 (UI 상태에서 추출)
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

            # 폴백: 기존 방식 (전체 액션 리스트)
            print(f"[State] 폴백: 전체 액션 리스트 생성 모드")
            try:
                if USE_MOCK_MODEL:
                    import mock_action_model as action_model_2
                else:
                    import action_model_2
                model_result = action_model_2.run_action_from_prompt(
                    prompt_text=PROMPT_TEXT,
                    max_new_tokens=256,
                    do_sample=False
                )

                if "generated_action" in model_result:
                    generated_action = model_result["generated_action"]
                    state_data_to_save["generated_action"] = generated_action
                    print(f"[State] 폴백 액션 생성 완료")

                    actions_file = generated_action.get("actions_file")
                    if isinstance(actions_file, list):
                        print(f"[State] 생성된 액션 개수: {len(actions_file)}개")
                else:
                    raise Exception("generated_action 없음")

            except Exception as e2:
                print(f"[State] 폴백도 실패: {e2}")
                # 최종 폴백: 하드코딩된 trajectory
                temp_action = {
                    "type": "trajectory",
                    "actions_file": "trajectory_student_check.json",
                    "description": "학적부 열람 (최종 폴백)"
                }
                state_data_to_save["generated_action"] = temp_action
                print(f"[State] 하드코딩 trajectory 사용")
        # ====================================

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

    # There is some task
    resp = {
        "has_task": True,
        "task_type": current_type,
    }

    if current_type == 1:
        # login task
        resp["type"] = "login"
        resp["student_id"] = STUDENT_ID
        resp["password"] = PASSWORD
        # 로그인 테스크 소비를 알림
        LOGIN_EVENT.set()
        # 로그인은 여기서 바로 소모되므로 타입 리셋
        TASK_TYPE = 0

    elif current_type == 2:
        resp["type"] = "state"
        resp["prompt_text"] = PROMPT_TEXT
        # TASK_TYPE을 3으로 변경 (다음은 액션 명령)
        TASK_TYPE = 3

    elif current_type == 3:
        # action task
        resp["type"] = "action"

        # One-Action-at-a-Time 모드: 다음 액션 미리 생성
        if ACTION_SESSION_ACTIVE:
            print(f"[Command] One-Action-at-a-Time 세션 활성화 - 다음 액션 생성 예약")
            # 실제 액션 생성은 /action 호출 후 이루어지므로 여기서는 플래그만 설정

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
        # 마지막 액션 → 완료
        print(f"[Action] 마지막 액션 전달 (status: FINISH), 작업 완료")
        TASK_TYPE = 0
        PROMPT_EVENT.set()
    else:
        # 중간 액션 → 다시 state 요청
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


    #로그인 세션 없음 → 로그인 해제 처리
    if not os.path.exists(login_path):
        print("[Status] 로그인 세션 없음 → 로그인 화면으로 복귀")
        return {
            "status": "waiting",
            "message": "로그인 세션이 없습니다. 다시 로그인하세요.",
            "data": {"loginSuccess": False},
        }

    #로그인 세션 존재하지만 state.json 없음 → idle (로그인 유지)
    if not os.path.exists(state_path):
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

    # state.json 존재 → 작업 상태 반환
    try:
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


    #state.json 파일이 존재하는 경우
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        #실행 완료 감지 → state.json 삭제 (이전 로직 유지)
        if "action_success" in data:
            try:
                os.remove(state_path)
                print("[Status] 실행 완료 감지 → state.json 삭제")
            except Exception as e:
                print(f"[Status] state.json 삭제 실패: {e}")

            return {"status": "completed", "data": data}

        # 실행 중 상태 유지
        print("[Status] 실행 중: state.json 존재, action_success 미포함")
        return {"status": "processing", "data": data}

    except Exception as e:
        print(f"[Status] 상태 파일 읽기 실패: {e}")
        return {
            "status": "error",
            "message": f"state.json 읽기 중 오류 발생: {str(e)}",
            "data": {"loginSuccess": False},
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


@app.post("/logout")
async def logout():
    """로그아웃 - 세션 및 브라우저 상태 초기화"""
    global STUDENT_ID, PASSWORD, PROMPT_TEXT, LOGIN_EVENT, PROMPT_EVENT, TASK_TYPE

    STUDENT_ID = None
    PASSWORD = None
    PROMPT_TEXT = None
    LOGIN_EVENT.set()
    PROMPT_EVENT.set()

    TASK_TYPE = 99  # 실행웹이 이 값을 보고 브라우저 종료 수행

    # 세션 및 상태 파일 삭제
    base_dir = os.path.dirname(__file__)
    for fname in ["login_state.json", "state.json"]:
        path = os.path.join(base_dir, fname)
        if os.path.exists(path):
            os.remove(path)
            print(f"[로그아웃] {fname} 삭제 완료")

    print("[백엔드] 로그아웃 요청 - 상태 초기화 완료")
    return {"ok": True, "message": "로그아웃 처리됨"}

@app.post("/browser/close")
async def close_browser():
    """브라우저 닫기 명령"""
    global TASK_TYPE
    TASK_TYPE = 4  # 브라우저 닫기 명령
    print("[백엔드] 브라우저 닫기 명령 설정")
    return {"ok": True, "message": "브라우저 닫기 명령 전송"}

@app.get("/execution_web/status")
async def execution_web_status():
    """실행 웹 연결 상태 확인"""
    global EXECUTION_WEB_CONNECTED, LAST_POLL_TIME, BROWSER_RUNNING, BROWSER_COUNT
    import datetime

    # 마지막 폴링으로부터 8초 이상 경과하면 연결 끊김으로 간주
    # (실행 웹은 5초마다 폴링하므로, 8초면 충분히 안전한 마진)
    if LAST_POLL_TIME:
        elapsed = (datetime.datetime.now() - LAST_POLL_TIME).total_seconds()
        if elapsed > 8:
            EXECUTION_WEB_CONNECTED = False
            # 연결이 끊기면 브라우저 상태도 초기화
            BROWSER_RUNNING = False
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

