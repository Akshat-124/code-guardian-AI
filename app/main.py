from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
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

class ReviewRequest(BaseModel):
    file_path: str
    code_content: str
    diff_content: Optional[str] = ""

class PatchRequest(BaseModel):
    file_path: str
    original_code: str
    corrected_code: str

@app.get("/")
def read_root():
    return {"status": "running", "service": "CodeGuardian AI"}

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
        
        return {
            "success": True,
            "file_reviewed": payload.file_path,
            "static_issues_count": len(static_issues),
            "final_report": result.get("final_report", "No report generated."),
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
    print(f"Received request to apply patch to file: {payload.file_path}")
    
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
