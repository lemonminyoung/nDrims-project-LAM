# -*- coding: utf-8 -*-
"""
Mock Action Model for Testing
모델 없이 One-Action-at-a-Time 흐름을 테스트하기 위한 Mock 모듈
"""

# ========== 전역 세션 상태 ==========
_current_step_index = 0

# ========== 수정 추가 (2025-11-19) ==========
# 문제: Render 서버가 재시작하지 않으면 _current_step_index가 초기화 안 됨
# 해결: 마지막 프롬프트를 저장해서 새 프롬프트 감지 시 초기화
_last_prompt = None  # ← 추가: 프롬프트 변경 감지용
# ========== 수정 끝 ==========

# Mock plan: 3단계
_mock_steps = [
    (1, "메인 페이지로 이동"),
    (2, "학적 메뉴 클릭"),
    (3, "학적부열람 클릭")
]

# Mock 액션 정의
_mock_actions = [
    # Step 1: 메인 페이지로 이동
    {
        "name": "goto",
        "args": {"url": "https://ndrims.dongguk.edu/main/main.clx"}
    },
    # Step 2: 학적 메뉴 클릭
    {
        "name": "click",
        "args": {"selector": "role=treeitem[name='학적/확인서']"}
    },
    # Step 3: 학적부열람 클릭
    {
        "name": "click",
        "args": {"selector": "role=treeitem[name='학적부열람']"}
    }
]


def get_next_action(observations=None, prompt_text=None, **kwargs):
    """
    Mock: 다음 액션 생성
    미리 정의된 액션을 순차적으로 반환

    ========== 수정 (2025-11-19) ==========
    추가 파라미터: prompt_text
    - 새 프롬프트 감지를 위해 추가
    - 프롬프트가 바뀌면 step_index 초기화
    ========================================
    """
    global _current_step_index, _last_prompt

    # ========== 디버그 로깅 추가 (2025-11-19) ==========
    print(f"[Mock DEBUG] 함수 시작 - _current_step_index: {_current_step_index}, _last_prompt: {_last_prompt}")
    print(f"[Mock DEBUG] 받은 prompt_text: {prompt_text}")
    # ========== 디버그 끝 ==========

    # ========== 수정 시작 (2025-11-19) ==========
    # 문제 1: 이전 실행이 완료된 상태(_current_step_index >= len)에서 새 요청이 오면 리셋 필요
    # 해결: 완료 상태에서 새 prompt_text가 오면 무조건 리셋
    if _current_step_index >= len(_mock_steps) and prompt_text:
        print(f"[Mock] 이전 실행 완료 상태에서 새 프롬프트 감지 → 강제 리셋")
        _current_step_index = 0
        _last_prompt = prompt_text
        print(f"[Mock DEBUG] 강제 리셋 후 - _current_step_index: {_current_step_index}")

    # 문제 2: observations로 첫 요청 감지가 불완전함 (첫 요청도 UI 상태 포함 가능)
    # 해결: prompt_text 변경으로 새 세션 감지
    elif prompt_text and prompt_text != _last_prompt:
        print(f"[Mock] 새 프롬프트 감지: '{prompt_text}', step_index 초기화")
        _current_step_index = 0
        _last_prompt = prompt_text
        print(f"[Mock DEBUG] 초기화 후 - _current_step_index: {_current_step_index}")
    # ========== 수정 끝 ==========

    # 모든 step 완료 (리셋 후에는 여기 안 옴)
    if _current_step_index >= len(_mock_steps):
        print(f"[Mock DEBUG] 모든 step 완료 (_current_step_index={_current_step_index} >= {len(_mock_steps)})")
        return {
            "generated_action": {
                "type": "trajectory",
                "action": None,
                "description": "All steps completed",
                "current_step": _current_step_index,
                "total_steps": len(_mock_steps)
            }
        }

    # 현재 step 정보
    sid, tplan = _mock_steps[_current_step_index]
    is_last_action = (_current_step_index == len(_mock_steps) - 1)

    print(f"[Mock DEBUG] 액션 생성 전 - _current_step_index: {_current_step_index}, is_last_action: {is_last_action}")

    action = _mock_actions[_current_step_index].copy()

    # 마지막 액션이면 status: "FINISH" 추가
    if is_last_action:
        action["status"] = "FINISH"
        print(f"[Mock] 마지막 액션에 status='FINISH' 추가")

    print(f"[Mock] 액션 생성: step {_current_step_index + 1}/{len(_mock_steps)} - {tplan}")
    if observations:
        print(f"[Mock] Observations 수신: {observations}")

    result = {
        "generated_action": {
            "type": "trajectory",
            "action": action,
            "description": tplan,
            "current_step": _current_step_index + 1,
            "total_steps": len(_mock_steps)
        }
    }

    # step index 증가
    print(f"[Mock DEBUG] 증가 전 - _current_step_index: {_current_step_index}")
    _current_step_index += 1
    print(f"[Mock DEBUG] 증가 후 - _current_step_index: {_current_step_index}")

    return result
