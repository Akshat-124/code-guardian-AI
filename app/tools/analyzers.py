import subprocess
import json
import re
import os

def run_bandit_scan(file_path: str) -> dict:
    """
    Runs Bandit static analysis scanner on a target python file.
    Returns parsed JSON results or fallback list of issues.
    """
    if not file_path.endswith('.py'):
        return {"success": False, "issues": [], "error": "Not a Python file"}

    if not os.path.exists(file_path):
        return {"success": False, "issues": [], "error": "File does not exist"}

    try:
        # Run bandit via subprocess
        # -f json returns structured output, -q runs quietly
        result = subprocess.run(
            ["bandit", "-f", "json", "-q", file_path],
            capture_output=True,
            text=True
        )
        
        # Bandit returns non-zero code if issues are found, so we check stdout/stderr instead of check=True
        if result.stdout:
            data = json.loads(result.stdout)
            issues = []
            for item in data.get("results", []):
                issues.append({
                    "line": item.get("line_number"),
                    "issue_text": item.get("issue_text"),
                    "severity": item.get("issue_severity"),
                    "confidence": item.get("issue_confidence"),
                    "code_snippet": item.get("code")
                })
            return {"success": True, "issues": issues}
        else:
            return {"success": True, "issues": [], "raw_stderr": result.stderr}
            
    except Exception as e:
        return {"success": False, "issues": [], "error": str(e)}


def run_regex_scanner(file_path: str) -> dict:
    """
    Scans files for patterns like secrets, passwords, connection strings, or obvious injections.
    Suitable for non-Python or general checks.
    """
    issues = []
    if not os.path.exists(file_path):
        return {"success": False, "issues": [], "error": "File does not exist"}

    # Pattern matchers
    PATTERNS = {
        "Hardcoded Secret": r"(?i)(api_key|secret_key|private_key|password|passwd|db_password)\s*=\s*['\"][a-zA-Z0-9_\-\+\/]{8,}['\"]",
        "Potential SQL Injection": r"(?i)(execute|query|select|insert|update)\(.*%s.*\)",
        "TODO Comment": r"(?i)#\s*TODO|//\s*TODO"
    }

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            line_num = idx + 1
            for issue_type, pattern in PATTERNS.items():
                if re.search(pattern, line):
                    # For TODO comment, keep it as Low severity info. Others as High/Medium
                    severity = "LOW" if "TODO" in issue_type else "HIGH"
                    issues.append({
                        "line": line_num,
                        "issue_text": f"Detected {issue_type}",
                        "severity": severity,
                        "confidence": "HIGH",
                        "code_snippet": line.strip()
                    })

        return {"success": True, "issues": issues}
    except Exception as e:
        return {"success": False, "issues": [], "error": str(e)}


def run_full_static_analysis(file_path: str) -> list:
    """
    Combines bandit scan (for python) and general regex scanner.
    """
    combined_issues = []
    
    # Run generic scanner first
    regex_res = run_regex_scanner(file_path)
    if regex_res.get("success"):
        combined_issues.extend(regex_res.get("issues", []))

    # Run bandit if Python file
    if file_path.endswith('.py'):
        bandit_res = run_bandit_scan(file_path)
        if bandit_res.get("success"):
            combined_issues.extend(bandit_res.get("issues", []))

    return combined_issues
