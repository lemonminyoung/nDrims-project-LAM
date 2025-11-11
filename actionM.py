import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---------------------------------------------
# 1. 모델 경로 설정
# ---------------------------------------------
MODEL_PATH = "Action_model_v1"  # 현재 폴더 기준 경로

# ---------------------------------------------
# 2. 모델 및 토크나이저 불러오기
# ---------------------------------------------
print("모델과 토크나이저 로드 중...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH)
model.to("cuda" if torch.cuda.is_available() else "cpu")
model.eval()
print("✅ 모델 로드 완료!")

# ---------------------------------------------
# 3. 사용자 입력 받기
# ---------------------------------------------
user_input = input("\n[User] 명령을 입력하세요: ")

# ---------------------------------------------
# 4. 대화 템플릿 구성
# ---------------------------------------------
messages = [
    {"role": "system", "content": "You are a helpful AI assistant developed by Kakao."},
    {"role": "user", "content": user_input},
]

# ---------------------------------------------
# 5. 입력을 모델 토큰 포맷으로 변환
# ---------------------------------------------
inputs = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True
)

input_ids = torch.tensor([inputs]).to(model.device)
input_length = input_ids.shape[1]

# ---------------------------------------------
# 6. 모델로부터 답변 생성
# ---------------------------------------------
with torch.no_grad():
    output = model.generate(
        input_ids,
        max_new_tokens=128,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=False  # True로 바꾸면 확률적 샘플링
    )

# ---------------------------------------------
# 7. 새로 생성된 부분만 추출 (입력 제외)
# ---------------------------------------------
generated_tokens = output[0][input_length:]
response = tokenizer.decode(generated_tokens, skip_special_tokens=True)

# ---------------------------------------------
# 8. 출력 결과 표시
# ---------------------------------------------
print("\n--- [Action 데이터] ---")
print(response)
print("-----------------------")

# ---------------------------------------------
# 9. (선택) JSON 형태로 자동 파싱 시도
# ---------------------------------------------
try:
    import json
    parsed = json.loads(response.replace("'", "\""))
    print("\n--- [JSON 파싱 결과] ---")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
except Exception as e:
    print("\n⚠️ JSON 형식이 완벽하지 않아 파싱하지 않았습니다.")