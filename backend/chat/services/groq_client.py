from django.conf import settings
from groq import Groq

from sdk.llm_logger import log_inference, log_inference_stream

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


@log_inference_stream(provider="groq")
def stream_chat(*, messages, model):
    # Groq includes usage on the final streamed chunk by default (no
    # stream_options needed — this SDK version doesn't accept that kwarg).
    stream = _client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        delta = choice.delta.content if choice and choice.delta else None
        usage = None
        if chunk.usage:
            usage = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
        yield {
            "delta": delta,
            "usage": usage,
            "finish_reason": choice.finish_reason if choice else None,
        }
