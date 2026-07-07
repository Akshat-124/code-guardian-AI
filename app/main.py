from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import uuid
from typing import Optional, List
from app.agents.graph import agent_graph
from app.tools.analyzers import run_full_static_analysis
from app.tools.patcher import apply_code_patch

app = FastAPI(
    title="CodeGuardian AI",
    description="Autonomous Multi-Agent Code Review & DevSecOps Platform API",
    version="1.0.0"
)

# Mount static files folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

class ReviewRequest(BaseModel):
    file_path: str
    code_content: str
    diff_content: Optional[str] = ""

class PatchRequest(BaseModel):
    file_path: str
    original_code: str
    corrected_code: str
    full_code: Optional[str] = None

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")

@app.post("/review")
def trigger_code_review(payload: ReviewRequest):
    """
    Simulates a pull request webhook trigger.
    Runs static analysis and routes through the LangGraph agents.
    """
    # Create temp directory for scanning
    temp_dir = "temp_src"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate a unique temp filename preserving original extension
    file_ext = payload.file_path.split('.')[-1] if '.' in payload.file_path else 'txt'
    temp_file_name = f"{uuid.uuid4()}.{file_ext}"
    temp_file_path = os.path.join(temp_dir, temp_file_name)
    
    try:
        # Write contents to temp file so static analysis tools (like bandit) can scan it
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(payload.code_content)
        
        print(f"Written temp file for analysis: {temp_file_path}")
        
        # Run static analyzers
        static_issues = run_full_static_analysis(temp_file_path)
        print(f"Static analyzer detected {len(static_issues)} potential issues.")
        
        # Initialize LangGraph state (with empty list for fixes reducer)
        initial_state = {
            "file_path": payload.file_path,
            "code_content": payload.code_content,
            "diff_content": payload.diff_content,
            "static_issues": static_issues,
            "security_report": "",
            "quality_report": "",
            "test_report": "",
            "doc_report": "",
            "final_report": "",
            "proposed_fixes": []
        }
        
        # Invoke Graph
        result = agent_graph.invoke(initial_state)
        
        final_report = result.get("final_report", "No report generated.")
        is_passed = bool(result.get("passed", False)) and "FAILED" not in final_report[:150].upper()
        
        # Write debug logs to disk for inspection
        try:
            os.makedirs("scratch", exist_ok=True)
            with open("scratch/debug_reports.json", "w", encoding="utf-8") as f:
                json.dump({
                    "passed": is_passed,
                    "final_report": final_report,
                    "security_report": result.get("security_report", ""),
                    "quality_report": result.get("quality_report", ""),
                    "test_report": result.get("test_report", ""),
                    "doc_report": result.get("doc_report", "")
                }, f, indent=2)
        except Exception as ex:
            print(f"Failed debug write: {ex}")
            
        return {
            "success": True,
            "file_reviewed": payload.file_path,
            "static_issues_count": len(static_issues),
            "passed": is_passed,
            "final_report": final_report,
            "security_report": result.get("security_report", ""),
            "quality_report": result.get("quality_report", ""),
            "test_report": result.get("test_report", ""),
            "doc_report": result.get("doc_report", ""),
            "proposed_fixes": result.get("proposed_fixes", [])
        }
        
    except Exception as e:
        print(f"Error executing review graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"Cleaned up temp file: {temp_file_path}")

@app.post("/apply-fix")
def apply_fix_endpoint(payload: PatchRequest):
    """
    Applies a generated code patch to a local file.
    """
    # If the file does not exist locally, write the initial full code first
    if not os.path.exists(payload.file_path) and payload.full_code:
        try:
            # Create folder structure if nested
            dir_name = os.path.dirname(payload.file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(payload.file_path, "w", encoding="utf-8") as f:
                f.write(payload.full_code)
            print(f"Initialized non-existent file {payload.file_path} with initial editor code.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create file: {e}")

    success = apply_code_patch(
        file_path=payload.file_path,
        original_code=payload.original_code,
        corrected_code=payload.corrected_code
    )
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Failed to apply patch. Please ensure the code matches the file contents."
        )
        
    return {"success": True, "message": "Patch applied successfully!"}


# --- GitHub Webhook CI/CD Integration Schemas ---
class GitFileChange(BaseModel):
    filename: str
    content: str

class GitPullRequestHead(BaseModel):
    ref: str
    sha: str

class GitPullRequestBase(BaseModel):
    ref: str

class GitPullRequestDetail(BaseModel):
    title: str
    head: GitPullRequestHead
    base: GitPullRequestBase

class GitHubWebhookPayload(BaseModel):
    action: str
    number: int
    pull_request: GitPullRequestDetail
    changes: List[GitFileChange]


@app.post("/webhook/github")
def github_webhook_endpoint(payload: GitHubWebhookPayload):
    """
    Simulates receiving a GitHub Webhook Pull Request event.
    Performs static scanning and LangGraph state review on all modified files,
    returning structured check status and PR review comment overlays.
    """
    print(f"[Webhook] Received PR webhook for PR #{payload.number} ('{payload.pull_request.title}')")
    
    annotations = []
    
    # Process each modified file in the changes list
    for file_change in payload.changes:
        filename = file_change.filename
        content = file_change.content
        
        # Save temp file for static scanner
        temp_dir = "temp_src"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"pr_{payload.number}_{filename}")
        
        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            # Run Bandit static scanning
            static_issues = run_full_static_analysis(temp_file_path)
            
            # Setup LangGraph initial state
            initial_state = {
                "file_path": filename,
                "code_content": content,
                "diff_content": "",
                "static_issues": static_issues,
                "security_report": "",
                "quality_report": "",
                "test_report": "",
                "doc_report": "",
                "final_report": "",
                "proposed_fixes": [],
                "passed": False
            }
            
            # Invoke review state machine
            result = agent_graph.invoke(initial_state)
            
            final_report = result.get("final_report", "No report generated.")
            is_passed = bool(result.get("passed", False)) and "FAILED" not in final_report[:150].upper()
            
            annotations.append({
                "filename": filename,
                "passed": is_passed,
                "static_issues_found": len(static_issues),
                "review_comment": final_report,
                "proposed_fixes_count": len(result.get("proposed_fixes", []))
            })
            
        except Exception as e:
            print(f"Error reviewing file {filename} in webhook: {e}")
            annotations.append({
                "filename": filename,
                "passed": False,
                "error": str(e)
            })
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    # Determine overall check success
    overall_passed = all(a.get("passed", False) for a in annotations)
    
    return {
        "status": "success",
        "pr_number": payload.number,
        "action": payload.action,
        "overall_checks_passed": overall_passed,
        "annotations": annotations
    }
