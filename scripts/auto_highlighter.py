import os
import re
import sys
import json
import requests

def highlight_with_gemini(heading, body, api_key):
    """
    Uses Google AI Studio (Gemini 2.5 Flash) to automatically insert premium highlights
    ([word](red), [word](orange), **bold**) in JSON format.
    """
    print("Using Google AI Studio (Gemini 2.5 Flash) to automatically highlight important words...")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        system_instruction = (
            "You are a professional graphic editor for a premium historical channel called 'ERASED'. "
            "Your task is to take a raw heading and body copy, and insert visual highlights using markdown-like tags:\n"
            "- Use `[word](red)` for crimson highlights on key visual topics, secret actions, and major terms (e.g., [secretly](red), [manipulated](red), [atomic](red), [decoded](red), [rate fixes](red)).\n"
            "- Use `[word](orange)` for orange highlights on proper nouns (people's names, organizations, banks, e.g. [Truman](orange), [Barclays](orange), [Julius and Ethel Rosenberg](orange)).\n"
            "- Use `**word**` to bold other key phrases or numbers for emphasis.\n\n"
            "Rules:\n"
            "1. Do NOT change, edit, correct, or rephrase any words in the text. The words must remain EXACTLY as input.\n"
            "2. Highlight count rules:\n"
            "   - Heading: Highlight exactly 2 to 3 key terms/phrases using colors (red or orange).\n"
            "   - Body: Highlight a maximum of 5 words/phrases using colors (red or orange). Bold a maximum of 3 other words/phrases in black (using **bold** syntax).\n"
            "3. Formatting rules:\n"
            "   - Do NOT escape the brackets. Return [word](red) or [word](orange), NOT \\[word\\](red) or \\[word\\](orange).\n"
            "   - Always use lowercase for color names. Use (red) or (orange), never (RED) or (ORANGE).\n"
            "   - Do NOT add spaces between the closing square bracket and opening parenthesis (e.g. use [word](red), NOT [word] (red)).\n"
            "4. Output MUST be valid JSON with keys 'heading' and 'body'. Do not include any formatting blocks outside the JSON."
        )
        user_content = json.dumps({
            "heading": heading,
            "body": body
        })
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "parts": [{"text": user_content}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                res_data = response.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                result = json.loads(raw_text)
                return result.get("heading", heading), result.get("body", body)
            except Exception as e:
                print(f"Highlight attempt {attempt + 1} failed: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print("Failed to highlight with Gemini after all retries.", file=sys.stderr)
                    return None
    except Exception as e:
        print(f"Failed to highlight with Gemini: {e}. Falling back to offline rule-based highlighting.", file=sys.stderr)
        return None

def highlight_with_rules(heading, body):
    """
    Offline fallback rule-based highlighter.
    Uses regex patterns to highlight numbers, quoted phrases, proper nouns, and key terms.
    """
    print("Using offline rule-based highlighter...")
    
    # 1. Red keywords (case-insensitive)
    red_keywords = [
        "manipulated", "secretly", "decoded", "atomic", "spies", "spy", 
        "convicted", "executed", "classified", "declassified", "penetrated", 
        "cracked", "intelligence", "communications", "defects", "disaster",
        "crisis", "malformations", "refused"
    ]
    
    # 2. Orange keywords (proper nouns/organizations that might be lowercase in lists)
    orange_keywords = [
        "Barclays", "Deutsche Bank", "UBS", "Truman", "Julius", "Ethel",
        "Rosenberg", "Rosenbergs", "NSA", "KGB", "VENONA", "LIBOR"
    ]

    def apply_rules(text, is_body=True):
        spans = [] # list of (start, end, tag_prefix, tag_suffix)
        
        # A. Highlight text inside double quotes in red
        for match in re.finditer(r'"([^"]+)"', text):
            start, end = match.start(1), match.end(1)
            spans.append((start, end, "[", "](red)"))
            
        # B. Highlight proper nouns in orange
        if is_body:
            for match in re.finditer(r'\b([A-Z][a-zA-Z\u00C0-\u017F]+(?:\s+[A-Z][a-zA-Z\u00C0-\u017F]+)*)\b', text):
                word = match.group(1)
                start = match.start(1)
                
                before = text[:start].strip()
                if not before or before.endswith('.') or before.endswith('!') or before.endswith('?'):
                    if word.lower() not in ["thalidomide", "grünenthal", "kelsey", "europe", "canada", "australia"]:
                        continue
                
                if word.lower() in ["in", "the", "on", "at", "a", "this", "after", "manufacturer", "disaster", "severe"]:
                    continue
                    
                spans.append((start, start + len(word), "[", "](orange)"))
                
        # C. Match specific red/orange keywords
        for word in red_keywords:
            for match in re.finditer(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE):
                spans.append((match.start(), match.end(), "[", "](red)"))
                
        for word in orange_keywords:
            for match in re.finditer(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE):
                spans.append((match.start(), match.end(), "[", "](orange)"))
                
        # D. Match numbers and years for bold highlights
        bold_patterns = [
            r'\b\d{1,3}(?:,\d{3})+\b', 
            r'\b\d+(?:\s*(?:years|years-old|decade|decades|months|days|settlements))\b',
            r'\b\d{4}s?\b'
        ]
        for pattern in bold_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                spans.append((match.start(), match.end(), "**", "**"))
                
        # Filter overlapping spans
        spans = sorted(spans, key=lambda x: (x[0], -(x[1] - x[0])))
        non_overlapping = []
        last_end = -1
        for start, end, prefix, suffix in spans:
            if start >= last_end:
                non_overlapping.append((start, end, prefix, suffix))
                last_end = end
                
        # Reconstruct text back to front
        result = text
        for start, end, prefix, suffix in sorted(non_overlapping, key=lambda x: x[0], reverse=True):
            word = result[start:end]
            if start > 0 and result[start-1] in ['[', '*']:
                continue
            result = result[:start] + f"{prefix}{word}{suffix}" + result[end:]
            
        return result

    return apply_rules(heading, is_body=False), apply_rules(body, is_body=True)

def auto_highlight(heading, body):
    """
    Main function to automatically format heading and body text with highlights.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if gemini_key:
        result = highlight_with_gemini(heading, body, gemini_key)
        if result:
            return result
            
    # Fallback to rules-based highlighting if Gemini is not available
    print("Warning: Gemini API Key missing or failed. Using offline rule-based fallback.", file=sys.stderr)
    return highlight_with_rules(heading, body)
