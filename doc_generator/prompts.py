INSPECT_FILES_PROMPT = """You are analyzing a Python codebase.
Given the following Python files, identify all logical modules (groups of related files).
For each module, provide:
- name: a short module name
- files: list of filenames that belong to it
- purpose: one sentence describing what it does

{format_instructions}

Files:
{file_list}
"""

IDENTIFY_CONTRACTS_PROMPT = """You are extracting API contracts from Python code.
Given the following code, extract:
- REST API endpoints (path, method, description, request_body, response, auth_required)
- Async events (event name and description)

{format_instructions}

Code:
{code}
"""

INFER_REQUIREMENTS_PROMPT = """You are a software analyst.
Given the following Python codebase, infer:
- functional_requirements: what the system does (list of strings)
- non_functional_requirements: quality attributes like performance, security (list of strings)
- project_name: short name for this project
- project_goal: one sentence summary of the project purpose

{format_instructions}

Code summary:
{code_summary}
"""

MODULE_DOC_PROMPT = """You are writing technical documentation for a software module.
Given the following code for the module '{module_name}', write documentation including:
- purpose: what this module does
- interfaces: list of public classes/functions with brief descriptions
- dependencies: other modules or libraries this depends on
- tech_stack: frameworks and libraries used
- key_classes: important class names
- key_functions: important function names
- notes: any important implementation details

{format_instructions}

Code:
{code}
"""

CRITIC_PROMPT = """You are reviewing auto-generated software documentation for quality.
Rate the documentation on a scale of 0-10 and list specific problems found.

{format_instructions}

Documentation:
{docs}
"""

FIX_DOCS_PROMPT = """You are improving software documentation based on reviewer feedback.
Fix the following problems in the documentation:
{problems}

Current documentation:
{docs}

Respond with the corrected documentation as valid JSON in the same format as the input.
"""
