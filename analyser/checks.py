from bs4 import BeautifulSoup
from collections import defaultdict
from analyser.nlp_checks import score_text_descriptiveness

def check_missing_alt(soup):
    images = soup.find_all("img")
    missing = [img for img in images if not img.get("alt") or img.get("alt").strip() == ""]
    return {
        "total": len(images),
        "missing": len(missing),
        "missing_elements": [str(img) for img in missing]
    }

def check_heading_structure(soup):
    headings = [(tag.name, tag) for tag in soup.find_all([f"h{i}" for i in range(1, 7)])]
    last_level = 0
    skipped = []
    for name, tag in headings:
        level = int(name[1])
        if last_level and level > last_level + 1:
            skipped.append(str(tag))
        last_level = level
    return {
        "total": len(headings),
        "skipped": len(skipped),
        "skipped_elements": skipped
    }

def check_form_labels(soup):
    inputs = soup.find_all("input")
    labels = {label.get("for") for label in soup.find_all("label") if label.get("for")}
    missing = [inp for inp in inputs if inp.get("type") != "hidden" and (not inp.get("id") or inp.get("id") not in labels)]
    return {
        "total": len(inputs),
        "missing": len(missing),
        "missing_elements": [str(inp) for inp in missing]
    }

def check_alt_text_quality(soup):
    images = soup.find_all("img")
    results = []
    for img in images:
        alt = img.get("alt", "").strip()
        score = score_text_descriptiveness(alt)
        results.append({
            "img": str(img),
            "alt": alt,
            "score": score["score"],
            "label": score["label"]
        })
    return results 