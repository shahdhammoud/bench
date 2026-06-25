"""
Type 14 — Documentation Violation Injector (LLM-based)

Injects bugs that violate specific claims made in the generated documentation.
Examples:
  - Doc says "returns a list" → code returns a dict
  - Doc says "raises ValueError on invalid input" → exception handling removed
  - Doc says "accepts optional parameter X" → parameter removed from signature
  - Doc says "normalizes input to lowercase" → normalization step removed

Uses self-consistency: calls LLM 3 times, takes the most common result.
"""

import ast
import json
from collections import Counter
from openai import OpenAI

INJECTOR_PROMPT = """You are a code injection assistant for a benchmark dataset.

You will receive:
1. A Python function or class (GOLD CODE)
2. Documentation describing what the code should do (DOCS)

Your task: inject a subtle bug into the code that VIOLATES a specific claim in the documentation.
The bug must be realistic and non-trivial — not just deleting everything.

Rules:
- Only modify the implementation, not the function signature or class name
- The violation must be traceable to a specific documentation claim
- Return ONLY a JSON object with no explanation outside it

GOLD CODE:
{gold_code}

DOCUMENTATION:
{docs}

Respond ONLY with this JSON:
{{
  "injected_code": "<full modified python code>",
  "violated_claim": "<exact quote or paraphrase of the doc claim being violated>",
  "injection_description": "<one sentence describing what was changed>"
}}"""


def _call_llm(client, model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


def _extract_result(raw: str) -> dict | None:
    """Extract JSON result from LLM response."""
    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def inject_doc_violation(
    gold_code: str,
    docs: str,
    client: OpenAI,
    model: str,
    n_votes: int = 3,
) -> dict:
    """
    Inject a documentation-violating bug using self-consistency voting.

    Args:
        gold_code: The correct Python source code
        docs: Generated documentation for the code
        client: OpenAI-compatible client
        model: Model name to use
        n_votes: Number of LLM calls for self-consistency (default 3)

    Returns:
        dict with keys: injected_code, violated_claim, injection_description, injected (bool)
    """
    prompt = INJECTOR_PROMPT.format(
        gold_code=gold_code[:4000],
        docs=docs[:2000],
    )

    results = []
    for i in range(n_votes):
        try:
            raw = _call_llm(client, model, prompt)
            parsed = _extract_result(raw)
            if parsed and parsed.get("injected_code"):
                # Validate syntax
                try:
                    ast.parse(parsed["injected_code"])
                    results.append(parsed)
                except SyntaxError:
                    print(f"  Vote {i+1}: syntax error in injected code, skipping")
            else:
                print(f"  Vote {i+1}: could not parse LLM response")
        except Exception as e:
            print(f"  Vote {i+1}: LLM error — {e}")

    if not results:
        return {
            "injected_code": gold_code,
            "violated_claim": "",
            "injection_description": "",
            "injected": False,
        }

    # Self-consistency vote: pick most common injected_code
    vote_counts = Counter(r["injected_code"] for r in results)
    best_code = vote_counts.most_common(1)[0][0]
    best_result = next(r for r in results if r["injected_code"] == best_code)

    # Final check: must differ from gold
    if best_result["injected_code"].strip() == gold_code.strip():
        return {
            "injected_code": gold_code,
            "violated_claim": "",
            "injection_description": "",
            "injected": False,
        }

    return {
        "injected_code": best_result["injected_code"],
        "violated_claim": best_result.get("violated_claim", ""),
        "injection_description": best_result.get("injection_description", ""),
        "injected": True,
        "problem_type": 14,
    }


if __name__ == "__main__":
    # Quick test on a simple example
    client = OpenAI(
        base_url="http://10.32.2.11:54000/v1",
        api_key="sk-litellm-token-hyper"
    )
    model = "qwen2.5-72b"

    test_code = '''
def get_user_email(user_id: int) -> str:
    """Fetch user email from database by user ID."""
    result = db.query(f"SELECT email FROM users WHERE id={user_id}")
    return result[0]["email"].lower()
'''
    test_docs = """
Function: get_user_email
- Accepts a user_id integer
- Queries the database for the user record
- Returns the email address normalized to lowercase
- Raises IndexError if user not found
"""

    print("Testing doc violation injector...")
    result = inject_doc_violation(test_code, test_docs, client, model)
    print(f"Injected: {result['injected']}")
    if result['injected']:
        print(f"Violated claim: {result['violated_claim']}")
        print(f"Description: {result['injection_description']}")
        print(f"Injected code:\n{result['injected_code']}")
