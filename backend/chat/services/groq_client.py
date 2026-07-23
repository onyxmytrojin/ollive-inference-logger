from django.conf import settings
from groq import Groq

from sdk.llm_logger import log_inference

_client = Groq(api_key=settings.GROQ_API_KEY)


@log_inference(provider="groq")
def complete_chat(*, messages, model):
    completion = _client.chat.completions.create(model=model, messages=messages)
    choice = completion.choices[0]
    usage = completion.usage

    return {
        "output": choice.message.content or "",
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "metadata": {
            "finish_reason": choice.finish_reason,
            "provider_request_id": completion.id,
        },
    }
