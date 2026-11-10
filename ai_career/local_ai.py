
"""Groq-powered career assistant helpers."""

import logging
import hashlib
import json

from django.core.cache import cache
from django.conf import settings
from groq import Groq
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are a helpful AI Career Copilot for a college placement system.

PERSONALIZATION:
- Use the student's actual branch, skills, projects, resume, and career interest.
- Give relevant advice to students from all academic branches.
- Never invent student details, jobs, companies, or eligibility requirements.

RESPONSE STYLE:
- Start with a direct answer to the student's question.
- Use clear headings and numbered steps where appropriate.
- Use bullet points for skills, recommendations, and examples.
- Explain technical concepts in simple language.
- Give practical examples relevant to the student's background.
- Avoid unnecessary introductions and repeated information.
- Adapt the response length to the question.

COMPLETENESS:
- Answer every part of the question.
- Finish all lists and explanations before ending.
- Do not intentionally stop halfway through an explanation.
- For longer topics, prioritize the most useful information.
- End with one clear, practical next action.

Use only the supplied student and job information when discussing
existing opportunities. Never claim to have performed actions
that you have not actually performed.
"""



def _create_client():
    api_key = getattr(settings, "GROQ_API_KEY", "")

    if not api_key:
        raise ValueError("Groq API key is not configured.")

    return Groq(
        api_key=api_key,
        timeout=20.0,
        max_retries=1,
    )



def _build_messages(question, student_context, conversation_history=None):
    """Build role-specific messages for Career Copilot."""

    if isinstance(student_context, str):
        try:
            context = json.loads(student_context)
        except (json.JSONDecodeError, TypeError):
            context = {}
    elif isinstance(student_context, dict):
        context = student_context
    else:
        context = {}

    role = str(context.get("role", "STUDENT")).upper()
    instructions = context.get("instructions", "")

    role_prompts = {
        "STUDENT": (
            "You are a student career advisor. Focus on skills, "
            "career paths, resumes, projects, interview preparation, "
            "and eligible job opportunities."
        ),
        "RECRUITER": (
            "You are a recruiter assistant. Focus on writing job "
            "descriptions, defining required skills, evaluating "
            "candidate suitability using available information, "
            "creating interview questions, and recruitment workflows. "
            "Do not assume the user is a student seeking a job."
        ),
        "ADMIN": (
            "You are a placement system administrator assistant. "
            "Focus on recruiter approvals, placement operations, "
            "platform management, recruitment workflows, and "
            "placement reporting. Do not assume the user is a student "
            "or a recruiter. Never invent statistics or claim to "
            "perform administrative actions you have not performed."
        ),
    }

    system_prompt = (
        "You are the AI Career Copilot for an AI-powered career "
        "and placement system.\n"
        f"Current user role: {role}\n"
        f"{role_prompts.get(role, role_prompts['STUDENT'])}\n"
        f"Additional role instructions: {instructions}\n"
        "Use the supplied context when relevant. If information is "
        "missing, say so instead of inventing it. Answer the user's "
        "actual question directly with clear headings and practical "
        "steps when useful."
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    if conversation_history:
        for item in conversation_history[-6:]:
            if item.get("role") in ("user", "assistant"):
                messages.append({
                    "role": item["role"],
                    "content": item.get("content", ""),
                })

    messages.append({
        "role": "user",
        "content": (
            f"User role: {role}\n"
            f"Available context: {json.dumps(context, ensure_ascii=False, default=str)}\n"
            f"Current question: {question}"
        ),
    })

    return messages



def generate_career_answer(
    question,
    student_context,
    conversation_history=None,
):
    """Generate a complete Groq response."""
    try:
        client = _create_client()

        response = client.chat.completions.create(
            model=getattr(
                settings,
                "GROQ_MODEL",
                "openai/gpt-oss-120b",
            ),
            messages=_build_messages(
                question,
                student_context,
                conversation_history,
            ),
            temperature=0.3,
            max_tokens=2500,
        )

        answer = response.choices[0].message.content

        if answer and answer.strip():
            return {
                "success": True,
                "answer": answer.strip(),
            }

        return {
            "success": False,
            "answer": "The AI returned an empty response. Please try again.",
        }

    except Exception:
        logger.exception("Groq career response failed")
        return {
            "success": False,
            "answer": (
                "The AI assistant is temporarily unavailable. "
                "Please try again later."
            ),
        }




def stream_career_answer(
    question,
    student_context,
    conversation_history=None,
):
    """
    Stream Groq responses, detect incomplete answers,
    and cache successfully completed answers for 5 minutes.
    """

    model = getattr(
        settings,
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )

    max_tokens = 2500
    response_parts = []
    finish_reason = None

    try:
        messages = _build_messages(
            question,
            student_context,
            conversation_history,
        )

        # Include generation settings in the cache key.
        cache_data = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_completion_tokens": max_tokens,
            },
            sort_keys=True,
            default=str,
        )

        cache_key = "career_copilot:" + hashlib.sha256(
            cache_data.encode("utf-8")
        ).hexdigest()

        # Return only previously completed answers.
        cached_answer = cache.get(cache_key)

        if cached_answer:
            yield {
                "type": "token",
                "content": cached_answer,
            }

            yield {"type": "done"}
            return

        client = _create_client()

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=max_tokens,
            stream=True,
        )

        # Read the Groq stream.
        for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            content = choice.delta.content

            if isinstance(content, str) and content:
                response_parts.append(content)

                yield {
                    "type": "token",
                    "content": content,
                }

        answer = "".join(response_parts).strip()

        # Detect output truncation before caching or marking complete.
        if finish_reason == "length":
            logger.warning(
                "Career Copilot reached its output limit. "
                "Model=%s, generated_chars=%s",
                model,
                len(answer),
            )

            yield {
                "type": "error",
                "content": (
                    "The answer reached the AI output limit and may be "
                    "incomplete. Please ask for a shorter or more focused "
                    "answer."
                ),
            }
            return

        # Handle content-filter interruptions.
        if finish_reason == "content_filter":
            logger.warning(
                "Career Copilot response stopped by a content filter. "
                "Model=%s",
                model,
            )

            yield {
                "type": "error",
                "content": (
                    "The response was stopped by a content filter. "
                    "Please rephrase your question and try again."
                ),
            }
            return

        # An answer must have content and a normal finish reason.
        if not answer:
            logger.error(
                "Groq returned an empty response. "
                "Model=%s, finish_reason=%s",
                model,
                finish_reason,
            )

            yield {
                "type": "error",
                "content": (
                    "The AI returned an empty response. Please try again."
                ),
            }
            return

        if finish_reason != "stop":
            logger.warning(
                "Career Copilot ended without a normal stop reason. "
                "Model=%s, finish_reason=%s",
                model,
                finish_reason,
            )

            yield {
                "type": "error",
                "content": (
                    "The AI connection ended before completion could be "
                    "confirmed. The answer may be incomplete. Please try "
                    "again."
                ),
            }
            return

        # Cache only successfully completed responses.
        cache.set(cache_key, answer, 300)

        # Tell the frontend that generation completed successfully.
        yield {"type": "done"}

    except Exception:
        logger.exception(
            "Groq streaming career response failed. Model=%s",
            model,
        )

        yield {
            "type": "error",
            "content": (
                "The AI assistant encountered an error while generating "
                "your response. Please try again."
            ),
        }

