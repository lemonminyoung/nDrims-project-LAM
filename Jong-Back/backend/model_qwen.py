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

        # pad 토큰이 없으면 eos로 설정(경고 방지)
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
        # Qwen은 일반 프롬프트로도 동작 (chat-template 미사용 단순 버전)
        inputs = self.tokenizer(prompt, return_tensors="pt")
        # device에 맞게 이동 (device_map='auto'일 때는 모델의 첫 디바이스로 보냄)
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

        # 전체(프롬프트+생성)에서 프롬프트 부분을 잘라 생성분만 반환
        generated = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        # 단순 분리: 프롬프트가 맨 앞에 붙어 있으므로 그 이후만
        if generated.startswith(prompt):
            return generated[len(prompt):].lstrip()
        return generated