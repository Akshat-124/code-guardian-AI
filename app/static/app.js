// Enterprise CodeGuardian AI Dashboard Javascript Engine
document.addEventListener("DOMContentLoaded", () => {
    
    // Lucide Icon activation
    lucide.createIcons();
    
    // UI Selectors
    const runAuditBtn = document.getElementById("run-audit-btn");
    const filePathInput = document.getElementById("file-path");
    
    const loadingOverlay = document.getElementById("loading-overlay");
    const emptyState = document.getElementById("empty-state");
    const resultsDashboard = document.getElementById("results-dashboard");
    
    const sideVulns = document.getElementById("side-vulns");
    
    const passedFailedBadge = document.getElementById("passed-failed-badge");
    const summaryParagraph = document.getElementById("findings-summary-paragraph");
    
    const reportView = document.getElementById("report-view");
    const fixesViewList = document.getElementById("fixes-view-list");
    
    // Initialize Monaco Editor via CDN loader
    let editor;
    require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' } });
    require(['vs/editor/editor.main'], function () {
        editor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
            value: `import sqlite3\n\nACCESS_TOKEN = "token_abc123xyz789_supersecret"\n\ndef fetch_user_record(username):\n    conn = sqlite3.connect('app.db')\n    cursor = conn.cursor()\n    cursor.execute("SELECT * FROM accounts WHERE name = '" + username + "'")\n    return cursor.fetchall()\n\ndef process():\n    try:\n        data = fetch_user_record("admin")\n        print("User data fetched successfully:", data)\n    except:\n        print("An error occurred")\n`,
            language: 'python',
            theme: 'vs-dark',
            automaticLayout: true,
            fontSize: 14,
            fontFamily: "'Fira Code', monospace",
            minimap: { enabled: false },
            lineHeight: 22,
            scrollbar: {
                vertical: 'visible',
                horizontal: 'visible',
                useShadows: false,
                verticalScrollbarSize: 8,
                horizontalScrollbarSize: 8
            }
        });
    });

    // Custom Markdown Simple HTML Parser
    function parseMarkdownToHtml(text) {
        if (!text) return "";
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Headers
        html = html.replace(/^# (.*?)$/gm, "<h2>$1</h2>");
        html = html.replace(/^## (.*?)$/gm, "<h2>$1</h2>");
        html = html.replace(/^### (.*?)$/gm, "<h3>$1</h3>");
        html = html.replace(/^#### (.*?)$/gm, "<h4>$1</h4>");
        
        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        
        // Bullet points
        html = html.replace(/^\* (.*?)$/gm, "<li>$1</li>");
        html = html.replace(/^- (.*?)$/gm, "<li>$1</li>");
        html = html.replace(/(<li>.*?<\/li>)+/g, "<ul>$&</ul>");
        
        // Inline code blocks
        html = html.replace(/`(.*?)`/g, "<code>$1</code>");
        
        // Fenced code blocks
        html = html.replace(/```python([\s\S]*?)```/g, "<pre class='diff-card-body' style='padding: 14px; margin-bottom:14px;'><code>$1</code></pre>");
        html = html.replace(/```([\s\S]*?)```/g, "<pre class='diff-card-body' style='padding: 14px; margin-bottom:14px;'><code>$1</code></pre>");
        
        // Double newlines
        html = html.replace(/\n\n/g, "<br><br>");
        
        return html;
    }
    
    // Tab Controller Trigger
    const tabButtons = document.querySelectorAll(".tab-btn");
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const targetTab = btn.getAttribute("data-tab");
            document.querySelectorAll(".tab-pane").forEach(pane => {
                pane.classList.remove("active");
            });
            document.getElementById(targetTab).classList.add("active");
        });
    });

    // Execute review audit pipeline call
    runAuditBtn.addEventListener("click", async () => {
        if (!editor) return;
        const codeValue = editor.getValue();
        const filePath = filePathInput.value;
        
        if (!codeValue.trim()) {
            alert("Workspace editor is empty. Please enter code to audit.");
            return;
        }
        
        // Loading states
        emptyState.classList.add("hidden");
        resultsDashboard.classList.add("hidden");
        loadingOverlay.classList.remove("hidden");
        runAuditBtn.disabled = true;
        
        try {
            const res = await fetch("/review", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    file_path: filePath,
                    code_content: codeValue,
                    diff_content: ""
                })
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Orchestration node failed.");
            }
            
            const result = await res.json();
            renderDashboardData(result, filePath);
            
        } catch (error) {
            alert(`Audit Execution Failed: ${error.message}`);
            emptyState.classList.remove("hidden");
            loadingOverlay.classList.add("hidden");
        } finally {
            runAuditBtn.disabled = false;
        }
    });

    // Render results layout
    function renderDashboardData(data, filePath) {
        loadingOverlay.classList.add("hidden");
        resultsDashboard.classList.remove("hidden");
        
        const staticIssuesCount = data.static_issues_count;
        const proposedFixes = data.proposed_fixes || [];
        const fixesCount = proposedFixes.length;
        
        // Read pass/fail status from backend
        const containsPassed = data.passed;
        
        if (containsPassed) {
            passedFailedBadge.innerText = "PASSED";
            passedFailedBadge.className = "badge passed";
            
            summaryParagraph.innerHTML = `<strong>Status: Secure</strong>. No high-risk exploit paths or database secrets detected. The code satisfies standard quality checks and is secure for release.`;
        } else {
            passedFailedBadge.innerText = "FAILED";
            passedFailedBadge.className = "badge failed";
            
            summaryParagraph.innerHTML = `<strong>Status: Vulnerable</strong>. Caught potential security risks (including bare exceptions, database connection leaks, or possible SQL injection issues). Review the action items below and apply fixes.`;
        }
        
        // Update values in sidebar
        sideVulns.innerText = staticIssuesCount;
        
        // Render markdown details for all multi-agent nodes
        reportView.innerHTML = parseMarkdownToHtml(data.final_report);
        document.getElementById("security-report-view").innerHTML = parseMarkdownToHtml(data.security_report);
        document.getElementById("quality-report-view").innerHTML = parseMarkdownToHtml(data.quality_report);
        document.getElementById("test-report-view").innerHTML = parseMarkdownToHtml(data.test_report);
        document.getElementById("doc-report-view").innerHTML = parseMarkdownToHtml(data.doc_report);
        
        // Render fixes tab list
        fixesViewList.innerHTML = "";
        
        if (proposedFixes.length === 0) {
            fixesViewList.innerHTML = `<div class="info-empty">No fixes proposed. Your script satisfies all standards.</div>`;
            return;
        }
        
        proposedFixes.forEach((fix, index) => {
            const desc = fix.description || "General code modification";
            const orig = fix.original_code;
            const corr = fix.corrected_code;
            
            if (!orig || !corr) return;
            
            const fixCard = document.createElement("div");
            fixCard.className = "fix-card-wrapper";
            
            // Format original and corrected code highlights
            let linesHtml = "";
            orig.trim().split('\n').forEach(ln => {
                linesHtml += `<div class="diff-ln del-line">- ${ln}</div>`;
            });
            corr.trim().split('\n').forEach(ln => {
                linesHtml += `<div class="diff-ln add-line">+ ${ln}</div>`;
            });
            
            fixCard.innerHTML = `
                <div class="fix-card-header">
                    <span class="fix-card-desc">Proposal ${index + 1}: ${desc}</span>
                </div>
                <div class="diff-card-body">
                    <div class="diff-grid">${linesHtml}</div>
                </div>
            `;
            
            fixesViewList.appendChild(fixCard);
        });
        
        lucide.createIcons();
    }
    
});
