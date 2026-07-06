import os
import json
import re
from typing import TypedDict, List, Dict, Any, Annotated
import operator
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langchain_groq import ChatGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from app import config
from app.tools.rag_store import query_relevant_rules

# 1. State Definition with List Reducer to accumulate fixes from parallel nodes
class AgentState(TypedDict):
    file_path: str
    code_content: str
    diff_content: str
    static_issues: List[Dict[str, Any]]
    security_report: str
    quality_report: str
    test_report: str
    doc_report: str
    final_report: str
    proposed_fixes: Annotated[List[Dict[str, Any]], operator.add]

# Helper to parse JSON autofixes from model outputs
def parse_autofix_json(response_text: str) -> list:
    """
    Parses structured autofix blocks from LLM text containing [START_AUTOFIX_JSON] ... [END_AUTOFIX_JSON].
    """
    pattern = r"\[START_AUTOFIX_JSON\](.*?)\[END_AUTOFIX_JSON\]"
    match = re.search(pattern, response_text, re.DOTALL)
    if not match:
        return []
    
    json_str = match.group(1).strip()
    try:
        # Strip potential markdown block syntax if model wraps it
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()
        
        data = json.loads(json_str)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []
    except Exception as e:
        print(f"Error parsing auto-fix JSON from LLM: {e}")
        return []

# Helper to check for API Key and initialize LLM
def get_llm():
    # 1. Check if model name suggests Groq
    groq_api_key = os.getenv("GROQ_API_KEY")
    if GROQ_AVAILABLE and groq_api_key and ("llama" in config.MODEL_NAME.lower() or "mixtral" in config.MODEL_NAME.lower()):
        try:
            return ChatGroq(
                model=config.MODEL_NAME,
                groq_api_key=groq_api_key,
                temperature=0.1
            )
        except Exception as e:
            print(f"Error initializing Groq LLM: {e}")
            
    # 2. Fallback to Gemini
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "YOUR_API_KEY":
        return None
    try:
        return ChatGoogleGenerativeAI(
            model=config.MODEL_NAME,
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.1
        )
    except Exception as e:
        print(f"Error initializing Gemini LLM: {e}")
        return None

# Node 1: Security Agent
def security_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Security Agent] Checking code...")
    llm = get_llm()
    
    issues_summary = "\n".join([
        f"- Line {i['line']}: {i['issue_text']} (Severity: {i['severity']})"
        for i in state["static_issues"]
    ]) if state["static_issues"] else "No static analysis issues flagged."

    if not llm:
        # Fallback response
        report = f"Mock Security Report for {state['file_path']}:\n"
        if state["static_issues"]:
            report += f"Found issues from static analysis:\n{issues_summary}"
        else:
            report += "No major security threats detected via static analysis."
        return {"security_report": report, "proposed_fixes": []}

    prompt = ChatPromptTemplate.from_template("""
You are an expert Application Security Engineer (AppSec).
Review the following code and the output from static analysis tools.
Verify if the static analysis flags are true positives, explain the risks, and propose fixes.

File: {file_path}
Static Scan Outputs:
{issues_summary}

Source Code:
```python
{code_content}
```

Format your response as a clear markdown report detailing:
1. Vulnerability verification (Explain why each is or isn't a true risk).
2. Any other security risks you spotted in the code that the static tool missed.
3. Recommended secure code fixes.

Additionally, you MUST output a structured JSON block containing the exact original code segment and the corrected code segment for each fix. Start the block with `[START_AUTOFIX_JSON]` and end it with `[END_AUTOFIX_JSON]` so it can be parsed. Ensure the code matches exactly.

Format the JSON block exactly like this:
[START_AUTOFIX_JSON]
[
  {{
    "description": "Short description of the security fix",
    "original_code": "exact lines of code to remove (must match code content exactly)",
    "corrected_code": "exact lines of code to insert"
  }}
]
[END_AUTOFIX_JSON]
""")

    chain = prompt | llm
    response = chain.invoke({
        "file_path": state["file_path"],
        "issues_summary": issues_summary,
        "code_content": state["code_content"]
    })
    
    content = response.content
    fixes = parse_autofix_json(content)
    clean_report = re.sub(r"\[START_AUTOFIX_JSON\].*?\[END_AUTOFIX_JSON\]", "", content, flags=re.DOTALL).strip()
    
    return {"security_report": clean_report, "proposed_fixes": fixes}


# Node 2: Quality Agent
def quality_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Quality Agent] Checking coding standards...")
    llm = get_llm()
    
    # RAG: Query relevant guidelines based on code context
    file_ext = state["file_path"].split('.')[-1] if '.' in state["file_path"] else "general"
    relevant_rules = query_relevant_rules(f"style guides and design rules for {file_ext} programming", limit=2)
    rules_text = "\n".join([f"- {r}" for r in relevant_rules]) if relevant_rules else "No matching guidelines found."

    if not llm:
        report = f"Mock Quality Report for {state['file_path']}:\nCode formatting conforms to standard guidelines.\nGuidelines used:\n{rules_text}"
        return {"quality_report": report, "proposed_fixes": []}

    prompt = ChatPromptTemplate.from_template("""
You are a Senior Software Quality Engineer.
Review the following code to evaluate code quality, modularity, readability, and naming standards.
Ensure it complies with the following coding standards (fetched from our DB):

Standards:
{rules_text}

Source Code:
```python
{code_content}
```

Format your response as a markdown report detailing:
1. Naming convention check (variables, functions, classes).
2. Code duplicate, complexity, and refactoring advice.
3. Logical improvements.

Additionally, you MUST output a structured JSON block containing the exact original code segment and the corrected code segment for each style/quality fix. Start the block with `[START_AUTOFIX_JSON]` and end it with `[END_AUTOFIX_JSON]` so it can be parsed. Ensure the code matches exactly.

Format the JSON block exactly like this:
[START_AUTOFIX_JSON]
[
  {{
    "description": "Short description of the quality fix",
    "original_code": "exact lines of code to remove (must match code content exactly)",
    "corrected_code": "exact lines of code to insert"
  }}
]
[END_AUTOFIX_JSON]
""")

    chain = prompt | llm
    response = chain.invoke({
        "rules_text": rules_text,
        "code_content": state["code_content"]
    })
    
    content = response.content
    fixes = parse_autofix_json(content)
    clean_report = re.sub(r"\[START_AUTOFIX_JSON\].*?\[END_AUTOFIX_JSON\]", "", content, flags=re.DOTALL).strip()
    
    return {"quality_report": clean_report, "proposed_fixes": fixes}


# Node 3: Test Agent
def test_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Test Agent] Reviewing coverage and drafting tests...")
    llm = get_llm()

    if not llm:
        report = f"Mock Test Agent Report for {state['file_path']}:\nAdd unit tests to verify parameters and return values."
        return {"test_report": report}

    prompt = ChatPromptTemplate.from_template("""
You are a Quality Assurance (QA) Automation Engineer.
Review the code and identify missing test coverage, edge cases, and write starter unit tests using a standard framework (e.g., pytest for python).

Source Code:
```python
{code_content}
```

Format your response as a markdown report detailing:
1. Untested paths or logical branches.
2. Edge cases to cover (null checks, range boundary, type checking).
3. Starter test code implementation.
""")

    chain = prompt | llm
    response = chain.invoke({"code_content": state["code_content"]})
    return {"test_report": response.content}


# Node 4: Documentation Agent
def doc_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Doc Agent] Checking docstrings...")
    llm = get_llm()

    if not llm:
        report = f"Mock Doc Agent Report for {state['file_path']}:\nEnsure all classes and methods have appropriate docstrings."
        return {"doc_report": report}

    prompt = ChatPromptTemplate.from_template("""
You are a Technical Writer.
Review the code for clear inline comments, modules/classes/functions docstrings.

Source Code:
```python
{code_content}
```

Format your response as a markdown report detailing:
1. Missing documentation (functions, public classes).
2. Proposed docstring updates in standard format.
""")

    chain = prompt | llm
    response = chain.invoke({"code_content": state["code_content"]})
    return {"doc_report": response.content}


# Node 5: Supervisor / Aggregator Agent
def supervisor_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Supervisor Agent] Aggregating agent findings...")
    llm = get_llm()

    reports = f"""
### 🛡️ Security Report
{state['security_report']}

### 🔍 Quality Report
{state['quality_report']}

### 🧪 Test Report
{state['test_report']}

### 📝 Documentation Report
{state['doc_report']}
"""

    fixes_markdown = ""
    valid_fixes = []
    
    # Filter out empty or broken entries
    if state.get("proposed_fixes"):
        for fix in state["proposed_fixes"]:
            if fix.get("original_code") and fix.get("corrected_code"):
                valid_fixes.append(fix)

    if valid_fixes:
        fixes_markdown = "\n\n### 🛠️ Proposed Auto-Fixes\n"
        for idx, fix in enumerate(valid_fixes):
            desc = fix.get("description", "Refactor change")
            orig = fix.get("original_code", "").strip()
            corr = fix.get("corrected_code", "").strip()
            fixes_markdown += f"\n#### Fix {idx + 1}: {desc}\n"
            fixes_markdown += "```diff\n"
            for line in orig.split('\n'):
                fixes_markdown += f"- {line}\n"
            for line in corr.split('\n'):
                fixes_markdown += f"+ {line}\n"
            fixes_markdown += "```\n"

    if not llm:
        final_summary = f"""# 🛡️ CodeGuardian AI Audit Report for: `{state['file_path']}`

## Summary of Findings (Mock Fallback Mode)
*All specialist agents completed review runs. Set API keys to activate AI generation.*

{reports}
{fixes_markdown}
"""
        return {"final_report": final_summary}

    prompt = ChatPromptTemplate.from_template("""
You are a Principal Software Engineer acting as the Lead Reviewer in a CI/CD pipeline.
Aggregate the reports from the specialized sub-agents into a single, cohesive, priority-sorted Pull Request review report.

Sub-Agent Reports:
{reports}

Produce a professional GitHub-flavored markdown report following these strict rules:
1. **Status Evaluation:** Determine if the code has passed the audit. If there are NO high-severity security issues (like SQL injection, hardcoded credentials, RCE bugs) and NO fatal quality concerns, mark the status as PASSED. Otherwise, mark it as FAILED.
2. **If status is PASSED:**
   - Begin the report with the header: `# 🛡️ CodeGuardian AI Check: PASSED ✅`
   - Provide a short, positive one-paragraph summary stating the code is secure and clean.
   - List any minor suggestions, docstring upgrades, or best practices under a "💡 Optional Best Practices & Enhancements" section. Do not list empty high-severity tables/lists.
3. **If status is FAILED:**
   - Begin the report with the header: `# 🛡️ CodeGuardian AI Check: FAILED ❌`
   - Provide a warning summary paragraph.
   - List the critical vulnerabilities sorted by severity (High, Medium, Low) with clear action items.
""")

    chain = prompt | llm
    response = chain.invoke({"reports": reports})
    
    # Append the fixes diff block to the final generated markdown report
    final_report = response.content + fixes_markdown
    return {"final_report": final_report}
