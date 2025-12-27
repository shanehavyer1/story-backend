import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# --- 1. CONFIGURATION ---
# We try to get the key from the Cloud Settings first.
# IF that fails, we use your specific key as the hardcoded backup.
GEMINI_KEY = os.environ.get("GEMINI_KEY", "AIzaSyADlsZDZmZXPvOL95su2qjLN_3-NK7mzRo")
genai.configure(api_key=GEMINI_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlayRequest(BaseModel):
    action: str

# --- 2. MEMORY SYSTEM ---
game_summary = "The adventure begins."
recent_history = [] 

# --- 3. ROBUST MODEL SELECTOR ---
def get_best_available_model():
    """
    Scans your API key permissions to find the best working model.
    Prevents 404 errors by never guessing a name that doesn't exist.
    """
    try:
        # Ask Google: "What models do I own?"
        all_models = list(genai.list_models())
        
        # Filter: Keep only models that can write text
        text_models = [m for m in all_models if 'generateContent' in m.supported_generation_methods]
        model_names = [m.name for m in text_models]
        
        if not model_names:
            # Emergency Backup
            print("DEBUG: No models found in list. Trying default.")
            return genai.GenerativeModel("gemini-pro")

        # --- SELECTION LOGIC ---
        # 1. Try to find the newest "1.5" version
        for name in model_names:
            if "gemini-1.5" in name:
                print(f"DEBUG: Selected Best Model -> {name}")
                return genai.GenerativeModel(name)
                
        # 2. If no 1.5, look for "Pro"
        for name in model_names:
            if "gemini-pro" in name:
                print(f"DEBUG: Selected Standard Model -> {name}")
                return genai.GenerativeModel(name)

        # 3. If neither exists, just grab the first one on the list
        fallback = model_names[0]
        print(f"DEBUG: Selected Fallback Model -> {fallback}")
        return genai.GenerativeModel(fallback)

    except Exception as e:
        print(f"Model Selection Error: {e}")
        return genai.GenerativeModel("gemini-pro")

# --- 4. GAME ENDPOINTS ---
@app.post("/play")
async def play_turn(request: PlayRequest):
    global recent_history, game_summary
    
    # Create the prompt context
    recent_text = "\n".join(recent_history)
    prompt = (
        f"You are the Dungeon Master. \n"
        f"--- JOURNAL ---\n{game_summary}\n"
        f"--- RECENT CHAT ---\n{recent_text}\n"
        f"PLAYER: {request.action}\n"
    )

    try:
        # Dynamically find the right tool for the job
        model = get_best_available_model()
        
        response = model.generate_content(prompt)
        story_text = response.text

        # Update Memory
        recent_history.append(f"Player: {request.action}")
        recent_history.append(f"DM: {story_text}")
        
        # Rolling Memory Buffer (Keep last 6 lines)
        if len(recent_history) > 6:
            recent_history = recent_history[2:]

        return {"story": story_text}

    except Exception as e:
        return {"story": f"System Error: {str(e)}"}

@app.post("/reset")
async def reset_game():
    global game_summary, recent_history
    game_summary = "The adventure begins."
    recent_history = []
    return {"message": "Reset complete."}

if __name__ == "__main__":
    # Get the correct port for the cloud, or use 8000 for local
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
