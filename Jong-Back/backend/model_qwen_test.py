# model_qwen.py
from typing import Optional
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

_MODEL_NAME = "Qwen/Qwen2-0.5B-Instruct"

class QwenGenerator:
    """
    Qwen-0.5B 텍스트 생성기.
    - 첫 호출 시 모델/토크나이저 로드(싱글톤).
    - thread-safe를 위해 .generate에서 torch.no_grad() 사용.
    """
    _instance: Optional["QwenGenerator"] = None

    def __init__(self):
        # device / dtype 설정
        self.device_map = "auto"  # GPU 있으면 자동 할당, 없으면 CPU
        self.torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        # 토크나이저/모델 로드
        self.tokenizer = AutoTokenizer.from_pretrained(
            _MODEL_NAME,
            trust_remote_code=True,
            use_fast=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            _MODEL_NAME,
            trust_remote_code=True,
            torch_dtype=self.torch_dtype,
            device_map=self.device_map
        )

        # pad 토큰 설정 (없을 경우 대비)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        if self.model.config.pad_token_id is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id

    @classmethod
    def get(cls) -> "QwenGenerator":
        if cls._instance is None:
            cls._instance = QwenGenerator()
        return cls._instance

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.95
    ) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        generated = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        if generated.startswith(prompt):
            return generated[len(prompt):].lstrip()
        return generated


# ✅ 테스트용 코드 추가
if __name__ == "__main__":
    qwen = QwenGenerator.get()
    user_prompt = input("👉 프롬프트를 입력하세요: ")
    result = qwen.generate(user_prompt, max_new_tokens=100)
    print("\n🤖 Qwen 응답:")
    print(result)