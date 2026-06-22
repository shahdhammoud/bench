# bench

> A benchmark dataset for evaluating and improving AI-powered code review agents on real-world Python codebases.

## Overview

`bench` is a research tool built as part of a supervised internship at ITMO University. It automatically constructs a high-quality benchmark dataset to test an AI code reviewer agent — a system that analyzes Python code against documentation to detect bugs.

The benchmark is built on top of [SWE-Bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified), a curated dataset of real GitHub bug fixes, and targets **12 distinct problem categories** identified through systematic analysis of human code review traces.

---

## Highlights

- ✅ **101 verified benchmark entries** across 5 major open-source repositories
- ✅ **12 problem types** covered, spanning rule-based and LLM-based defect classes
- ✅ **Average documentation quality score: 7.08 / 10** (critic-loop verified)
- ✅ **Zero identical gold/buggy pairs** — all injections produce meaningful, testable differences
- ✅ **Self-consistency voting** on all LLM-based injectors (3-sample majority)
- ✅ Fully automated pipeline from SWE-Bench task → benchmark entry

---

## What Each Entry Contains

| Field | Description |
|-------|-------------|
| `gold_code` | Correct Python code extracted from a real GitHub bug fix |
| `buggy_code` | The same code with a realistic, deliberate bug injected |
| `documentation` | Auto-generated structured documentation for the task |
| `injections` | JSON record: what was changed, where, and which problem type |
| `critic_score` | Quality score assigned by the doc generator's critic loop |

---

## Problem Types Covered

Derived from analysis of human reviewer traces across multiple real-world software modules:

|Problem Type | Method |
|--------------|--------|
|Architecture / model reuse | LLM-based |
|Interface / signature mismatches | Rule-based |
|Data model implementation errors | LLM-based |
|Field mapping / conversion mistakes | Rule-based |
|Wrong field access | Rule-based |
|Broad exception handling | Rule-based |
|Fake data in implementation | LLM-based |
|Test duplication | Rule-based |
|Forbidden mocking in tests | Rule-based |
|Missing real functionality tests | LLM-based |
|Missing scenario / preconditions | LLM-based |
|Wrong test expectations | LLM-based |

---

## Repositories Used

| Repository | Domain |
|------------|--------|
| [astropy/astropy](https://github.com/astropy/astropy) | Astronomy / scientific computing |
| [sympy/sympy](https://github.com/sympy/sympy) | Symbolic mathematics |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | Testing framework |
| [psf/requests](https://github.com/psf/requests) | HTTP library |
| [django/django](https://github.com/django/django) | Web framework |

---

## Architecture

### Doc Generator

A LangGraph workflow that produces structured documentation from source code:

```
inspect_files → identify_contracts → infer_requirements
     → generate_module_docs → run_critic → fix_docs
                                   ↑______________|
                              (loops up to 3x if score < threshold)
```

- Uses `PydanticOutputParser` with `get_format_instructions()` for structured output
- Critic scores documentation 0–10; `fix_docs` rewrites and re-scores until quality threshold is met
- All prompts grounded in actual source code — no hallucinated content

### Injectors

**7 rule-based injectors** use AST parsing for precise, deterministic changes:
- Examples: replace `except ValueError` → `except Exception`, change return type annotations, swap dictionary keys

**6 LLM-based injectors** use **self-consistency voting**:
- LLM called 3 times per injection
- Return statements extracted from each response
- `Counter.most_common()` selects the majority result
- Ensures stable, reproducible injections

### Assembly Pipeline

`assemble_benchmark.py` automates the full end-to-end process:

1. Takes a SWE-Bench task → clones repo at exact base commit → applies gold patch
2. Runs doc generator on gold code → scored and critic-verified documentation
3. Runs 1–5 injectors → produces buggy variants
4. Quality-gates each entry (score ≥ 6.5, gold ≠ buggy)
5. Saves to `data/benchmark.json`

---

## Repository Structure

```
bench/
├── doc_generator/           # LangGraph documentation generation workflow
│   ├── workflow.py
│   ├── nodes.py
│   └── prompts.py
├── injectors/               # 13 bug injectors (rule-based + LLM-based)
│   ├── injector_broad_exception.py
│   ├── injector_wrong_field_access.py
│   ├── injector_interface_mismatch.py
│   ├── injector_test_duplication.py
│   ├── injector_forbidden_mocking.py
│   ├── injector_field_mapping.py
│   ├── injector_fake_data.py
│   ├── injector_wrong_test_expectations.py
│   ├── injector_missing_functionality_tests.py
│   ├── injector_missing_scenario.py
│   ├── injector_architecture_reuse.py
│   └── injector_data_model.py
├── assemble_benchmark.py    # End-to-end pipeline script
├── parser/parser.py         # Documentation format parser
└── data/
    └── benchmark.json       # Final benchmark dataset (101 entries)
```

---

## Quality Assurance

Every entry in the benchmark passes through automated quality checks:

- **Critic loop**: documentation is scored and rewritten until it meets the quality threshold
- **Injection verification**: entries are only saved when the injector confirms a real change was made (`injected == true`)
- **Diff check**: gold and buggy code are compared — identical pairs are automatically discarded
- **Score gate**: entries scoring below 6.5 are excluded from the final dataset

---

## Environment

- Python: `openhands-ai-py3.12`
- Orchestration: LangGraph
- Output parsing: LangChain `PydanticOutputParser`
- Source data: [SWE-Bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified)

---

## Author

**Shahd Hammoud**  
Research Internship — ITMO University  
Supervisor: Maria Khodorchenko 
