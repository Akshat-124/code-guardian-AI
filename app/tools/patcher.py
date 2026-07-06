import os

def apply_code_patch(file_path: str, original_code: str, corrected_code: str) -> bool:
    """
    Finds the original_code block in the file_path and replaces it with corrected_code.
    Returns True if successfully patched, False otherwise.
    """
    if not os.path.exists(file_path):
        print(f"Patcher Error: Target file {file_path} does not exist.")
        return False
        
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        original_clean = original_code.strip()
        corrected_clean = corrected_code.strip()
        
        if not original_clean:
            print("Patcher Error: Original code block is empty.")
            return False

        # Attempt 1: Exact substring replacement
        if original_clean in content:
            updated_content = content.replace(original_clean, corrected_clean, 1)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return True
            
        # Attempt 2: Normalize line endings to resolve Windows CRLF mismatches
        content_norm = content.replace("\r\n", "\n")
        original_norm = original_clean.replace("\r\n", "\n")
        corrected_norm = corrected_clean.replace("\r\n", "\n")
        
        if original_norm in content_norm:
            updated_content_norm = content_norm.replace(original_norm, corrected_norm, 1)
            # Restore CRLF if needed
            if "\r\n" in content:
                updated_content_norm = updated_content_norm.replace("\n", "\r\n")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content_norm)
            return True
            
        # Attempt 3: Line-by-line matching ignoring leading/trailing whitespaces
        # This resolves indentation shifts
        lines = content.splitlines()
        orig_lines = original_clean.splitlines()
        
        match_idx = -1
        # Find where orig_lines start matching
        for i in range(len(lines) - len(orig_lines) + 1):
            match = True
            for j in range(len(orig_lines)):
                if lines[i + j].strip() != orig_lines[j].strip():
                    match = False
                    break
            if match:
                match_idx = i
                break
                
        if match_idx != -1:
            # Reconstruct content replacing matched lines with corrected_code
            # Try to preserve indentation of the first line of original block
            orig_indent = len(lines[match_idx]) - len(lines[match_idx].lstrip())
            indent_str = " " * orig_indent
            
            # Apply indentation to each line of corrected code
            corr_indented_lines = []
            for cline in corrected_clean.splitlines():
                corr_indented_lines.append(indent_str + cline if cline.strip() else cline)
                
            # Replace target slice
            lines[match_idx : match_idx + len(orig_lines)] = corr_indented_lines
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True

        print(f"Patcher Error: Could not locate original code block in file.")
        return False
        
    except Exception as e:
        print(f"Patcher Error: Exception occurred during patch write: {e}")
        return False
