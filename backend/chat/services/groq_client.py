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


TITLE_SYSTEM_PROMPT = (
    "Generate a short, specific title (3-6 words, no quotes, no trailing "
    "punctuation) summarizing what this conversation is about."
)


@log_inference(provider="groq")
def _complete_title(*, messages, model):
    completion = _client.chat.completions.create(model=model, messages=messages, max_tokens=20)
    choice = completion.choices[0]
    usage = completion.usage

    return {
        "output": (choice.message.content or "").strip().strip('"'),
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "metadata": {
            "purpose": "title_generation",
            "finish_reason": choice.finish_reason,
        },
    }


def generate_title(user_message, assistant_message, model, conversation_id=None):
    # A real inference call in its own right (costs tokens, hits the same
    # provider), so it goes through the same @log_inference path as chat
    # completions — tagged via metadata.purpose so it's distinguishable on
    # the dashboard rather than being hidden from the observability pipeline.
    return _complete_title(
        messages=[
            {"role": "system", "content": TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": f"User: {user_message}\nAssistant: {assistant_message}"},
        ],
        model=model,
        conversation_id=conversation_id,
    )["output"]
