import os
import sys
import requests

def generate_photo_prompt(heading, body):
    """
    Generates a visual photo prompt for the thumbnail based on heading and body text.
    First tries Google AI Studio (Gemini 2.5 Flash).
    Otherwise, falls back to a simple keyword-based prompt.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if gemini_key:
        print("Using Google AI Studio (Gemini 2.5 Flash) to automatically generate image prompt...")
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            headers = {
                "Content-Type": "application/json"
            }
            system_instruction = (
                "You are a creative prompt engineer for an AI image generator (like Flux or DALL-E). "
                "The image will be used as a thumbnail for a documentary-style historical channel called 'ERASED'. "
                "The channel focuses on secrets, espionage, Cold War, history, classified files, and mysteries.\n\n"
                "Given the heading and body of a post, generate a single, highly detailed, atmospheric image prompt.\n"
                "Rules:\n"
                "1. The Heading must be the absolute primary concept/focal point of the image. The visual subject must directly align with what is written in the Heading.\n"
                "2. Use the Body text ONLY to provide historical context, correct era (e.g. 1930s, 1960s), setting details, and mood elements to ground the image in historical accuracy.\n"
                "3. The style must be moody, cinematic, retro, vintage, with dramatic lighting (chiaroscuro) and historical realism.\n"
                "4. Do NOT include any text, letters, words, titles, logos, or labels in the image description.\n"
                "5. Keep the description visual: focus on lighting, texture, camera angles, color tones (e.g., warm sepia, dark navy, amber glow), and shadows.\n"
                "6. Return ONLY the final prompt string. No intro, no markdown, no quotes."
            )
            user_content = f"Heading:\n{heading}\n\nBody:\n{body}"
            
            payload = {
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "contents": [
                    {
                        "parts": [{"text": user_content}]
                    }
                ]
            }
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            res_data = response.json()
            generated_prompt = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if generated_prompt.startswith('"') and generated_prompt.endswith('"'):
                generated_prompt = generated_prompt[1:-1]
            print(f"Generated Prompt (Gemini): {generated_prompt}")
            return generated_prompt
        except Exception as e:
            print(f"Failed to generate prompt via Gemini: {e}.", file=sys.stderr)
            
    # Fallback to a simple keyword-based prompt if Gemini is not available
    print("Warning: Gemini API Key missing or failed. Using offline generic prompt fallback.", file=sys.stderr)
    return f"Atmospheric documentary photography style illustration representing: {heading}"
