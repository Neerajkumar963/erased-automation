import os
import requests
import sys

def generate_image(prompt, output_path):
    """
    Generates an image based on the prompt using configured AI APIs.
    Checks environment variables:
      1. FAL_KEY (using fal-ai/flux/schnell)
    Falls back to returning False if no key is set or generation fails.
    """
    fal_key = os.environ.get("FAL_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if gemini_key:
        print("Using Google AI Studio (Imagen 3) to generate image...")
        try:
            import base64
            url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={gemini_key}"
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "instances": [
                    {
                        "prompt": prompt
                    }
                ],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1",
                    "outputMimeType": "image/jpeg"
                }
            }
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            res_data = response.json()
            img_b64 = res_data["predictions"][0]["bytesBase64Encoded"]
            img_data = base64.b64decode(img_b64)
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Generated image saved to {output_path}")
            return True
        except Exception as e:
            print(f"Google Imagen 3 generation failed: {e}. Trying other APIs...", file=sys.stderr)

    if fal_key:
        flux_model = os.environ.get("FLUX_MODEL", "fal-ai/flux/schnell")
        print(f"Using Fal.ai ({flux_model}) to generate image...")
        try:
            url = f"https://queue.fal.run/{flux_model}"
            headers = {
                "Authorization": f"Key {fal_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": prompt,
                "image_size": "square",
                "sync_mode": True
            }
            if "schnell" in flux_model:
                payload["num_inference_steps"] = 4
                
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            res_data = response.json()
            image_url = res_data["images"][0]["url"]
            print(f"Downloading generated image from: {image_url}")
            img_data = requests.get(image_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Generated image saved to {output_path}")
            return True
        except Exception as e:
            print(f"Fal.ai generation failed: {e}", file=sys.stderr)

    print("No API key configured for Google Imagen or Fal.ai. Falling back to Pollinations.ai...")
    try:
        import urllib.parse
        import urllib.request
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            img_data = response.read()
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"Generated image saved to {output_path}")
        return True
    except Exception as e:
        print(f"Pollinations.ai generation failed: {e}", file=sys.stderr)
        return False

