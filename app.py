from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from bs4 import BeautifulSoup
import requests
from analyser import checks
import io
import csv
import subprocess
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sqlite3

app = FastAPI()

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, url: str = Form(None), file: UploadFile = File(None)):
    html_content = None
    axe_results = None
    if url:
        try:
            response = requests.get(url)
            response.raise_for_status()
            html_content = response.text
            # Run axe-core via Node.js subprocess
            proc = subprocess.run([
                "node", "run_axe.js", url
            ], capture_output=True, timeout=90)
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            if proc.returncode == 0 and stdout:
                try:
                    axe_results = json.loads(stdout)
                except Exception as e:
                    axe_results = {"error": f"Failed to parse axe-core output: {e}", "raw": stdout}
            else:
                axe_results = {"error": stderr or "No output from axe-core", "raw": stdout}
        except Exception as e:
            return templates.TemplateResponse("results.html", {"request": request, "error": f"Failed to fetch URL: {e}", "results": None, "url": url, "axe_results": None})
    elif file:
        html_content = (await file.read()).decode("utf-8", errors="ignore")
    else:
        return templates.TemplateResponse("results.html", {"request": request, "error": "No input provided.", "results": None, "url": None, "axe_results": None})

    soup = BeautifulSoup(html_content, "html.parser")
    alt_result = checks.check_missing_alt(soup)
    heading_result = checks.check_heading_structure(soup)
    form_label_result = checks.check_form_labels(soup)
    alt_quality = checks.check_alt_text_quality(soup)

    # Run C++ static analyzer
    cpp_analysis = None
    try:
        cpp_proc = subprocess.run([
            os.path.join("cpp_analyser", "build", "accessibility_cpp_analyser.exe")
        ], input=html_content.encode("utf-8"), capture_output=True, timeout=30)
        if cpp_proc.returncode == 0:
            cpp_analysis = json.loads(cpp_proc.stdout.decode("utf-8"))
        else:
            cpp_analysis = {"error": cpp_proc.stderr.decode("utf-8", errors="replace")}
    except Exception as e:
        cpp_analysis = {"error": str(e)}

    results = {
        "alt": alt_result,
        "headings": heading_result,
        "form_labels": form_label_result,
        "alt_quality": alt_quality,
        "cpp_analysis": cpp_analysis
    }

    # Prepare severity data for Chart.js bar chart
    # We'll treat missing alt, heading skips, missing labels, and C++ ARIA as 'errors' (no warnings in custom checks)
    severity_data = {
        'categories': ['Alt Text', 'Headings', 'Form Labels', 'ARIA (C++)'],
        'errors': [
            alt_result['missing'],
            heading_result['skipped'],
            form_label_result['missing'],
            cpp_analysis['missing_aria'] if cpp_analysis and 'missing_aria' in cpp_analysis else 0
        ],
        'warnings': [0, 0, 0, 0]  # No warnings in custom checks
    }
    # Add axe-core violations by impact if available
    if axe_results and isinstance(axe_results, dict) and 'violations' in axe_results:
        impact_map = {'critical': 0, 'serious': 0, 'moderate': 0, 'minor': 0}
        for v in axe_results['violations']:
            impact = v.get('impact', 'minor')
            if impact in impact_map:
                impact_map[impact] += 1
        severity_data['axe'] = impact_map
    else:
        severity_data['axe'] = {'critical': 0, 'serious': 0, 'moderate': 0, 'minor': 0}

    # Prepare issue type data for Chart.js pie chart
    issue_type_data = {
        'labels': ['Alt Text', 'Headings', 'Form Labels', 'ARIA (C++)', 'axe-core'],
        'counts': [
            alt_result['missing'],
            heading_result['skipped'],
            form_label_result['missing'],
            cpp_analysis['missing_aria'] if cpp_analysis and 'missing_aria' in cpp_analysis else 0,
            len(axe_results['violations']) if axe_results and isinstance(axe_results, dict) and 'violations' in axe_results else 0
        ]
    }

    # Insert scan result into SQLite
    try:
        conn = sqlite3.connect('scans.db')
        c = conn.cursor()
        c.execute('''INSERT INTO scans (url, alt_issues, heading_issues, form_label_issues, aria_issues, axe_critical, axe_serious, axe_moderate, axe_minor)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            url or 'uploaded_file',
            results['alt']['missing'],
            results['headings']['skipped'],
            results['form_labels']['missing'],
            results['cpp_analysis']['missing_aria'] if results['cpp_analysis'] and 'missing_aria' in results['cpp_analysis'] else 0,
            severity_data['axe']['critical'] if 'axe' in severity_data else 0,
            severity_data['axe']['serious'] if 'axe' in severity_data else 0,
            severity_data['axe']['moderate'] if 'axe' in severity_data else 0,
            severity_data['axe']['minor'] if 'axe' in severity_data else 0
        ))
        conn.commit()
        conn.close()
    except Exception as db_exc:
        print('DB insert error:', db_exc)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    template_name = "results_fragment.html" if is_ajax else "results.html"
    return templates.TemplateResponse(template_name, {"request": request, "results": results, "error": None, "url": url, "axe_results": axe_results, "severity_data": severity_data, "issue_type_data": issue_type_data})

@app.get("/download_report")
def download_report(url: str = None):
    if not url:
        return HTMLResponse("<h3>No URL provided for report download.</h3>", status_code=400)
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        return HTMLResponse(f"<h3>Failed to fetch URL: {e}</h3>", status_code=400)
    soup = BeautifulSoup(html_content, "html.parser")
    alt_result = checks.check_missing_alt(soup)
    heading_result = checks.check_heading_structure(soup)
    form_label_result = checks.check_form_labels(soup)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Check", "Total", "Issues Found"])
    writer.writerow(["Images missing alt text", alt_result["total"], alt_result["missing"]])
    writer.writerow(["Skipped heading levels", heading_result["total"], heading_result["skipped"]])
    writer.writerow(["Inputs missing labels", form_label_result["total"], form_label_result["missing"]])
    writer.writerow([])
    writer.writerow(["Details"])
    writer.writerow(["Images missing alt text:"])
    for el in alt_result["missing_elements"]:
        writer.writerow([el])
    writer.writerow([""])
    writer.writerow(["Skipped heading levels:"])
    for el in heading_result["skipped_elements"]:
        writer.writerow([el])
    writer.writerow([""])
    writer.writerow(["Inputs missing labels:"])
    for el in form_label_result["missing_elements"]:
        writer.writerow([el])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=accessibility_report.csv"})

@app.get("/report_trend.png")
def report_trend_png(url: str = None):
    conn = sqlite3.connect('scans.db')
    c = conn.cursor()
    if url:
        c.execute('SELECT timestamp, alt_issues, heading_issues, form_label_issues, aria_issues, axe_critical, axe_serious, axe_moderate, axe_minor FROM scans WHERE url = ? ORDER BY timestamp', (url,))
    else:
        c.execute('SELECT timestamp, alt_issues, heading_issues, form_label_issues, aria_issues, axe_critical, axe_serious, axe_moderate, axe_minor FROM scans ORDER BY timestamp')
    rows = c.fetchall()
    conn.close()
    if not rows:
        # Fallback to mock data if no scans
        x = np.arange(1, 11)
        y = np.random.randint(10, 100, size=10)
    else:
        x = np.arange(1, len(rows) + 1)
        y = [r[1] + r[2] + r[3] + r[4] + r[5] + r[6] + r[7] + r[8] for r in rows]  # sum all issue columns
    plt.figure(figsize=(5, 2.5))
    plt.plot(x, y, marker='o', color='#1976d2', linewidth=2)
    plt.title('Accessibility Issues Over Time')
    plt.xlabel('Scan #')
    plt.ylabel('Total Issues')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    from io import BytesIO
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")

@app.get("/history_data")
def history_data(url: str = None):
    conn = sqlite3.connect('scans.db')
    c = conn.cursor()
    if url:
        c.execute('SELECT timestamp, alt_issues, heading_issues, form_label_issues, aria_issues, axe_critical, axe_serious, axe_moderate, axe_minor FROM scans WHERE url = ? ORDER BY timestamp', (url,))
    else:
        c.execute('SELECT timestamp, alt_issues, heading_issues, form_label_issues, aria_issues, axe_critical, axe_serious, axe_moderate, axe_minor FROM scans ORDER BY timestamp')
    rows = c.fetchall()
    conn.close()
    data = {
        'labels': [r[0] for r in rows],
        'totals': [r[1] + r[2] + r[3] + r[4] + r[5] + r[6] + r[7] + r[8] for r in rows]
    }
    return JSONResponse(content=data) 