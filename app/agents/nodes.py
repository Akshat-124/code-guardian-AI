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
    passed: bool

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
                temperature=0.1,
                max_retries=6
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
            temperature=0.1,
            max_retries=6
        )
    except Exception as e:
        print(f"Error initializing Gemini LLM: {e}")
        return None

# Node 1: Security Agent
# Node: Unified DevSecOps Reviewer Agent (Optimized to prevent concurrent rate limits)
def devsecops_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[DevSecOps Agent] Running unified multi-agent inspection...")
    llm = get_llm()
    
    # Format static analysis scanner warnings
    issues = state.get("static_issues", [])
    issues_summary = ""
    if issues:
        for idx, i in enumerate(issues):
            issues_summary += f"- [{i.get('severity', 'LOW')}] Line {i.get('line', '?')}: {i.get('issue_text', i.get('description', 'Static warning'))}\n"
    else:
        issues_summary = "No static analyzer issues flagged."

    # RAG: Query style guides
    file_ext = state["file_path"].split('.')[-1] if '.' in state["file_path"] else "general"
    relevant_rules = query_relevant_rules(f"style guides and design rules for {file_ext} programming", limit=2)
    rules_text = "\n".join([f"- {r}" for r in relevant_rules]) if relevant_rules else "No matching guidelines found."

    if not llm:
        return {
            "security_report": "Mock Security Report: Scanner warnings verified.",
            "quality_report": "Mock Quality Report: Formatting complies with standards.",
            "test_report": "Mock Test Report: Basic pytest scaffolding created.",
            "doc_report": "Mock Doc Report: All public API methods documented.",
            "proposed_fixes": []
        }

    prompt = ChatPromptTemplate.from_template("""
You are an expert Application Security Engineer (AppSec), Senior Software Quality Engineer, QA Automation Engineer, and Technical Writer.
Review the following code carefully.

File: {file_path}
Static Scan Outputs:
{issues_summary}

Style Guidelines:
{rules_text}

Source Code:
```python
{code_content}
```

Produce a professional review report containing exactly these headers (do not modify the emojis or header names):

## 🛡️ Security Audit
Verify the static scan outputs. If any true security risks (like SQL injection, hardcoded secrets, pickle deserialization, or RCE) are present, explain them. If none, state "No major security threats detected."

## 🔍 Code Quality
Verify the modularity and syntax structure. Flag any unclosed file handles, resource leaks, raw threading locks (which could lead to deadlocks), or extreme nesting conditions.

## 🧪 Unit Tests
Provide a pytest unit testing script to cover the main functions of the code.

## 📝 Docs Audit
Flag any missing docstrings or arguments in the methods.

## 🛠️ Proposed Auto-Fixes
If you want to suggest any corrections, write them as diff cards exactly in this format (repeat for each fix):

#### Fix 1: Brief description of the fix
```diff
- line of original code to remove (must match source code exactly)
+ line of corrected code to insert
```
""")

    chain = prompt | llm
    response = chain.invoke({
        "file_path": state["file_path"],
        "issues_summary": issues_summary,
        "rules_text": rules_text,
        "code_content": state["code_content"]
    })
    
    content = response.content
    
    # Helper regex to extract section contents between headers
    def extract_section(header, next_headers):
        pattern = r"## " + re.escape(header) + r"\s*\n(.*?)(?=" + "|".join([r"## " + re.escape(h) for h in next_headers]) + r"|$)"
        m = re.search(pattern, content, re.DOTALL)
        return m.group(1).strip() if m else f"No findings for {header}."

    sec_rep = extract_section("🛡️ Security Audit", ["🔍 Code Quality", "🧪 Unit Tests", "📝 Docs Audit", "🛠️ Proposed Auto-Fixes"])
    qual_rep = extract_section("🔍 Code Quality", ["🛡️ Security Audit", "🧪 Unit Tests", "📝 Docs Audit", "🛠️ Proposed Auto-Fixes"])
    test_rep = extract_section("🧪 Unit Tests", ["🛡️ Security Audit", "🔍 Code Quality", "📝 Docs Audit", "🛠️ Proposed Auto-Fixes"])
    doc_rep = extract_section("📝 Docs Audit", ["🛡️ Security Audit", "🔍 Code Quality", "🧪 Unit Tests", "🛠️ Proposed Auto-Fixes"])
    
    # Parse proposed diff fixes
    fixes = []
    fix_matches = re.finditer(r"#### Fix \d+: (.*?)\n```diff\n(.*?)\n```", content, re.DOTALL)
    for m in fix_matches:
        desc = m.group(1).strip()
        diff_lines = m.group(2).split('\n')
        orig_lines = []
        corr_lines = []
        for line in diff_lines:
            if line.startswith('-'):
                # Strip leading '-' and preserve remaining whitespace
                orig_lines.append(line[1:])
            elif line.startswith('+'):
                # Strip leading '+' and preserve remaining whitespace
                corr_lines.append(line[1:])
        if orig_lines and corr_lines:
            fixes.append({
                "description": desc,
                "original_code": "\n".join(orig_lines),
                "corrected_code": "\n".join(corr_lines)
            })
            
    return {
        "security_report": sec_rep,
        "quality_report": qual_rep,
        "test_report": test_rep,
        "doc_report": doc_rep,
        "proposed_fixes": fixes
    }


def supervisor_agent_node(state: AgentState) -> Dict[str, Any]:
    print("[Supervisor Agent] Programmatically compiling findings...")
    
    # 1. Deterministic Pass/Fail Classification
    passed_bool = True
    
    # Fail if static analysis tools found anything on disk
    if len(state.get("static_issues", [])) > 0:
        passed_bool = False
        
    # Check Security Report for clean indicators
    sec_report = state.get("security_report", "")
    sec_lower = sec_report.lower()
    
    # Check for explicit safe statements
    has_clean_indicators = (
        "no major security threats" in sec_lower or 
        "no security issues" in sec_lower or 
        "no vulnerabilities" in sec_lower or 
        "no major security risks" in sec_lower or
        "no security threats" in sec_lower
    )
    
    if not has_clean_indicators:
        passed_bool = False
        
    # Check Quality Report for deadlock or file leak bugs
    qual_report = state.get("quality_report", "")
    qual_lower = qual_report.lower()
    if "deadlock" in qual_lower or "resource leak" in qual_lower or "unclosed file" in qual_lower:
        passed_bool = False

    # 2. Build Status Header and Summary Paragraph
    if passed_bool:
        status_header = "# 🛡️ CodeGuardian AI Check: PASSED ✅"
        summary_text = "**Status: Secure**. The codebase satisfies all critical Application Security (AppSec) parameters and modular programming standards. No high-risk exploit vectors (such as SQL Injection, Secrets leaks, or RCE) or thread concurrency deadlocks were detected."
    else:
        status_header = "# 🛡️ CodeGuardian AI Check: FAILED ❌"
        summary_text = "**Status: FAILED / Vulnerable**. The codebase contains potential security risks or coding standard lints that must be addressed before deployment. Review the action items and proposed fixes below."

    # 3. Stitch Reports together
    final_report = f"""{status_header}

{summary_text}

## Detailed Inspection Logs

### 🛡️ Security Audit
{state['security_report']}

### 🔍 Code Quality
{state['quality_report']}

### 🧪 Unit Tests
{state['test_report']}

### 📝 Docs Audit
{state['doc_report']}
"""

    # 4. Format Proposed Fixes Diffs
    fixes_markdown = ""
    valid_fixes = []
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

    final_report += fixes_markdown
    
    return {"final_report": final_report, "passed": passed_bool}
