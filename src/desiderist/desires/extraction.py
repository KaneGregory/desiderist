from desiderist.desires.models import Desire, ExtractionResult
from desiderist.llm.base import LLMProvider, Message, Role

EXTRACTION_SYSTEM_PROMPT = """\
You track a user's desires (goals or wants) as they emerge in conversation, as part of a
harness that will autonomously plan and take actions to fulfill them. Because a
downstream planning step acts on whatever you report, only report a change when the
user's message actually supports it — do not infer desires from speculation,
hypotheticals, or passing mentions.

Given the user's currently tracked active desires and their latest message, decide what,
if anything, changed. Respond with a list of operations:

- create: a new desire was expressed that isn't already tracked
- update: an existing desire's description, priority, or confidence changed
- fulfill: an existing desire has been satisfied
- abandon: the user no longer wants an existing desire, with no replacement
- contradict: the user now wants the opposite of an existing desire (the old desire is
  superseded and a new one is created — set `description` to the new desire's description)

If nothing changed, return an empty list of operations. Every operation must include a
`reasoning` field explaining why you made that call. For `update`, `fulfill`, `abandon`,
and `contradict`, set `desire_id` to the id of the existing desire being affected.
"""


def _format_active_desires(desires: list[Desire]) -> str:
    if not desires:
        return "(none)"
    return "\n".join(f"- [{d.id}] {d.description} (priority={d.priority}, confidence={d.confidence})" for d in desires)


def extract_desire_ops(
    provider: LLMProvider,
    *,
    active_desires: list[Desire],
    recent_turns: list[Message],
    new_message: str,
) -> ExtractionResult:
    system = f"{EXTRACTION_SYSTEM_PROMPT}\nCurrently active desires:\n{_format_active_desires(active_desires)}"
    messages = [*recent_turns, Message(role=Role.USER, content=new_message)]
    return provider.extract_structured(messages, system=system, schema=ExtractionResult)
