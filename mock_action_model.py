# -*- coding: utf-8 -*-
"""
Mock Action Model for Testing
모델 없이 One-Action-at-a-Time 흐름을 테스트하기 위한 Mock 모듈
"""

# 전역 세션 상태
_mock_session = {
    "user_request": None,
    "steps": [],
    "current_step_index": 0,
}

def init_action_session(prompt_text: str, **kwargs):
    """
    Mock: 세션 초기화
    테스트용으로 3단계 plan 생성
    """
    global _mock_session

    print(f"[Mock] 세션 초기화: {prompt_text}")

    # Mock plan: 3단계
    steps = [
        (1, "메인 페이지로 이동"),
        (2, "학적 메뉴 클릭"),
        (3, "학적부열람 클릭")
    ]

    _mock_session = {
        "user_request": prompt_text,
        "steps": steps,
        "current_step_index": 0,
    }

    return {
        "status": "initialized",
        "total_steps": len(steps),
        "user_request": prompt_text
    }


def get_next_action(observations=None, **kwargs):
    """
    Mock: 다음 액션 생성
    미리 정의된 액션을 순차적으로 반환
    """
    global _mock_session

    if not _mock_session["user_request"]:
        return {
            "error": "Session not initialized"
        }

    steps = _mock_session["steps"]
    current_idx = _mock_session["current_step_index"]

    # 모든 step 완료
    if current_idx >= len(steps):
        return {
            "generated_action": {
                "type": "trajectory",
                "action": None,
                "description": "All steps completed",
                "current_step": current_idx,
                "total_steps": len(steps)
            }
        }

    # 현재 step 정보
    sid, tplan = steps[current_idx]
    is_last_action = (current_idx == len(steps) - 1)

    # Mock 액션 정의
    mock_actions = [
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

    action = mock_actions[current_idx].copy()

    # 마지막 액션이면 status: "FINISH" 추가
    if is_last_action:
        action["status"] = "FINISH"
        print(f"[Mock] 마지막 액션에 status='FINISH' 추가")

    # step index 증가
    _mock_session["current_step_index"] += 1

    print(f"[Mock] 액션 생성: step {current_idx + 1}/{len(steps)} - {tplan}")
    if observations:
        print(f"[Mock] Observations 수신: {observations}")

    return {
        "generated_action": {
            "type": "trajectory",
            "action": action,
            "description": tplan,
            "current_step": current_idx + 1,
            "total_steps": len(steps)
        }
    }


def run_action_from_prompt(prompt_text: str, **kwargs):
    """
    Mock: 전체 액션 리스트 반환 (폴백용)
    """
    print(f"[Mock] 전체 액션 리스트 생성 (폴백 모드)")

    actions_file = [
        {"action": {"name": "goto", "args": {"url": "https://ndrims.dongguk.edu/main/main.clx"}}},
        {"action": {"name": "click", "args": {"selector": "role=treeitem[name='학적/확인서']"}}},
        {"action": {"name": "click", "args": {"selector": "role=treeitem[name='학적부열람']"}}}
    ]

    return {
        "generated_action": {
            "type": "trajectory",
            "actions_file": actions_file,
            "description": "학적부 조회 (Mock 전체 리스트)"
        }
    }
