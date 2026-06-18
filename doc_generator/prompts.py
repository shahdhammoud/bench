INSPECT_FILES_PROMPT = """You are analyzing a Python source file.
Identify logical modules based strictly on what is present in the file.
Do NOT invent modules that are not represented in the code.
For each module provide:
- name: a short module name derived from the file or class names
- files: list of filenames that belong to it
- purpose: one sentence describing what it does based only on the code
{format_instructions}
Files:
{file_list}
"""

IDENTIFY_CONTRACTS_PROMPT = """You are extracting API contracts from Python code.
Only extract REST endpoints and async events that are explicitly defined in the code.
If there are no REST endpoints or async events in the code, return empty lists. Do NOT invent any.
{format_instructions}
Code:
{code}
"""

INFER_REQUIREMENTS_PROMPT = """You are a software analyst reading a single Python source file.
Based strictly on the code provided, infer:
- functional_requirements: what functions/behaviors the code actually implements (derive from function names, docstrings, logic)
- non_functional_requirements: quality attributes you can observe in the code (e.g. error handling, type hints, performance considerations)
- project_name: short name derived from the module name or top-level docstring
- project_goal: one sentence summary based only on what the code actually does
Do NOT invent requirements that are not evidenced by the code.
{format_instructions}
Code summary:
{code_summary}
"""

MODULE_DOC_PROMPT = """You are writing technical documentation for a Python module.
Base everything strictly on the provided code. Do NOT invent or assume anything not present in the code.
If the file is a test file (filename starts with test_ or ends with _test.py):
- purpose: describe what functionality is being tested based on the test function names and assertions
- interfaces: list each test function with a description of what it verifies
- dependencies: only libraries actually imported in the code
- tech_stack: only frameworks/libraries in the import statements
- key_classes: only class names that exist in the code
- key_functions: list all test function names with one-line descriptions of what they test
- notes: any special fixtures, parametrize decorators, or setup/teardown observed in the code
Otherwise for regular source files:
- purpose: what this module does based on its functions and docstrings
- interfaces: list only the public functions and classes that actually exist in the code
- dependencies: only libraries actually imported in the code
- tech_stack: only frameworks/libraries in the import statements
- key_classes: only class names that exist in the code
- key_functions: only function names that exist in the code
- notes: implementation details observable in the code
{format_instructions}
Code:
{code}
"""

CRITIC_PROMPT = """You are reviewing auto-generated documentation produced from a single Python source file.
Rate the documentation on a scale of 0-10 and list specific problems.
Evaluate strictly on these criteria:
1. Accuracy — do the described functions, classes, and behavior match the actual code?
2. Completeness — are all major functions and classes in the code covered?
3. Clarity — are descriptions precise and unambiguous?
4. Grounding — does the documentation avoid inventing things not present in the code (e.g. fake dependencies, fabricated requirements)?
Do NOT deduct points for missing API endpoints, installation guides, or licensing if they are not present in the source file.
{format_instructions}
Documentation:
{docs}
"""

FIX_DOCS_PROMPT = """You are improving auto-generated documentation for a single Python source file.
Fix only the specific problems listed below. Base all fixes strictly on the source code provided.
Problems to fix:
{problems}
Current documentation:
{docs}
Source code:
{source_code}
{format_instructions}
"""
