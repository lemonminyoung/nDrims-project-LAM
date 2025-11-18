# -*- coding: utf-8 -*-
"""
Mock Action Model for Testing
모델 없이 One-Action-at-a-Time 흐름을 테스트하기 위한 Mock 모듈
"""

# 전역 세션 상태
_current_step_index = 0

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


def get_next_action(observations=None, **kwargs):
    """
    Mock: 다음 액션 생성
    미리 정의된 액션을 순차적으로 반환
    """
    global _current_step_index

    # 모든 step 완료
    if _current_step_index >= len(_mock_steps):
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
    _current_step_index += 1

    return result
