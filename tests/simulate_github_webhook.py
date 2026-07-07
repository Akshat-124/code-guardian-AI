import requests
import json
import sys

def main():
    print("=" * 60)
    print("CodeGuardian AI: GitHub Webhook CI/CD Simulator")
    print("=" * 60)
    
    # 1. Define Simulated File Changes
    secure_code = """
def calculate_factorial(n: int) -> int:
    \"\"\"
    Safely calculates the factorial of a non-negative integer.
    \"\"\"
    if n < 0:
        raise ValueError("Factorial is not defined for negative integers.")
    if n == 0 or n == 1:
        return 1
        
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
"""

    buggy_code = """
import sqlite3
import subprocess

def unsafe_login(username: str, system_cmd: str) -> None:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Vulnerability: SQL Injection
    query = f"SELECT * FROM accounts WHERE name = '{username}'"
    cursor.execute(query)
    
    # Vulnerability: Command Injection (RCE)
    subprocess.Popen(f"ping {system_cmd}", shell=True)
"""

    # 2. Build GitHub Pull Request Payload
    payload = {
        "action": "opened",
        "number": 104,
        "pull_request": {
            "title": "Feature: Integrate math utility and auth service",
            "head": {
                "ref": "feature-integration",
                "sha": "a1b2c3d4e5f6g7h8i9j0"
            },
            "base": {
                "ref": "main"
            }
        },
        "changes": [
            {
                "filename": "math_utils.py",
                "content": secure_code
            },
            {
                "filename": "auth_service.py",
                "content": buggy_code
            }
        ]
    }
    
    url = "http://127.0.0.1:8000/webhook/github"
    print(f"\nSending mock webhook payload for PR #104 to: {url}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to the CodeGuardian AI server.")
        print("Please make sure your FastAPI server is running (python run.py) on port 8000.")
        sys.exit(1)
        
    if response.status_code != 200:
        print(f"\n[ERROR] Server returned error status {response.status_code}:")
        print(response.text)
        sys.exit(1)
        
    data = response.json()
    
    print("\n" + "=" * 60)
    print("GITHUB PR CHECK ANNOTATIONS & COMMENTS")
    print("=" * 60)
    print(f"Pull Request: #{data['pr_number']}")
    print(f"Action: {data['action'].upper()}")
    print(f"Overall Build Status: {'PASSED' if data['overall_checks_passed'] else 'FAILED'}")
    print("-" * 60)
    
    for idx, annotation in enumerate(data.get("annotations", [])):
        print(f"\n[{idx + 1}] File: {annotation['filename']}")
        print(f"    Check Status: {'PASSED' if annotation['passed'] else 'FAILED'}")
        print(f"    Static Warnings Found: {annotation['static_issues_found']}")
        print(f"    Proposed Fixes Count: {annotation['proposed_fixes_count']}")
        print("\n    PR Review Comment Overlay:")
        # Indent the markdown response for clear readability
        review_lines = annotation['review_comment'].split('\n')
        for line in review_lines[:15]: # Show first 15 lines of review
            # Replace emojis in markdown text to prevent terminal encoding failures
            safe_line = line.replace("🛡️", "[SECURITY]").replace("🔍", "[QUALITY]").replace("🧪", "[TESTS]").replace("📝", "[DOCS]").replace("✅", "[PASSED]").replace("❌", "[FAILED]")
            print(f"      {safe_line}")
        if len(review_lines) > 15:
            print("      ... [truncated for CLI space] ...")
        print("-" * 60)
        
    print("\nSimulation execution finished successfully.")

if __name__ == "__main__":
    main()
