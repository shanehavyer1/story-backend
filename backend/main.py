import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# --- 1. SECURE CONFIGURATION ---
# The code now ONLY looks for the key in the Cloud Settings (Render).
# It will NOT work if you don't have the key in the Render Environment Variables.
GEMINI_KEY = os.environ.get("GEMINI_KEY")

if not GEMINI_KEY:
    print("CRITICAL WARNING: GEMINI_KEY is missing from environment variables!")
else:
    genai.configure(api_key=GEMINI_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows your Netlify frontend to connect
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Models ---
class PlayRequest(BaseModel):
    action: str

class StartRequest(BaseModel):
    genre: str

# --- 2. MEMORY SYSTEM ---
game_summary = "The adventure begins."
recent_history = [] 

# --- 3. ROBUST MODEL SELECTOR ---
def get_best_available_model():
    """
    Since you are Tier 1, this will prioritize the best models (1.5)
    but keeps the backup logic just in case.
    """
    try:
        if not GEMINI_KEY: return None

        all_models = list(genai.list_models())
        text_models = [m for m in all_models if 'generateContent' in m.supported_generation_methods]
        model_names = [m.name for m in text_models]
        
        if not model_names: return genai.GenerativeModel("gemini-pro")

        # Priority 1: Gemini 1.5 (Best for Tier 1 users)
        for name in model_names:
            if "gemini-1.5" in name: return genai.GenerativeModel(name)
            
        # Priority 2: Gemini Pro
        for name in model_names:
            if "gemini-pro" in name: return genai.GenerativeModel(name)

        # Priority 3: First available
        return genai.GenerativeModel(model_names[0])

    except Exception as e:
        print(f"Model Error: {e}")
        return genai.GenerativeModel("gemini-pro")

def update_summary(old_text):
    global game_summary
    try:
        model = get_best_available_model()
        prompt = f"Summarize into journal: {game_summary} \n Add these events: {old_text}"
        response = model.generate_content(prompt)
        if response.text:
            game_summary = response.text.strip()
    except:
        pass

# --- 4. ENDPOINTS ---

@app.post("/start")
async def start_game(request: StartRequest):
    """Starts a new game with a specific Genre."""
    global game_summary, recent_history
    recent_history = []
    
    game_summary = f"The player has started a {request.genre} adventure."
    
    try:
        model = get_best_available_model()
        prompt = f"You are a Dungeon Master for a {request.genre} game. Describe the starting scene in 2 sentences. Address the player directly."
        response = model.generate_content(prompt)
        opening_scene = response.text
    except:
        opening_scene = "You stand at the beginning of your adventure."

    return {"message": "Game Started", "opening": opening_scene}

@app.post("/play")
async def play_turn(request: PlayRequest):
    global recent_history, game_summary
    
    recent_text = "\n".join(recent_history)
    prompt = (
        f"You are the Dungeon Master. \n"
        f"--- JOURNAL ---\n{game_summary}\n"
        f"--- RECENT CHAT ---\n{recent_text}\n"
        f"PLAYER: {request.action}\n"
    )

    try:
        model = get_best_available_model()
        response = model.generate_content(prompt)
        story_text = response.text

        recent_history.append(f"Player: {request.action}")
        recent_history.append(f"DM: {story_text}")
        
        # Keep memory short (last 6 turns), summarize the rest
        if len(recent_history) > 6:
            update_summary("\n".join(recent_history[:2]))
            recent_history = recent_history[2:]

        return {"story": story_text}

    except Exception as e:
        return {"story": f"Error: {str(e)}"}

@app.post("/undo")
async def undo_turn():
    """Removes the last turn."""
    global recent_history
    if len(recent_history) >= 2:
        recent_history.pop()
        recent_history.pop()
        return {"message": "Undone", "remaining": recent_history}
    return {"message": "Nothing to undo"}

@app.post("/reset")
async def reset_game():
    global game_summary, recent_history
    game_summary = "The adventure begins."
    recent_history = []
    return {"message": "Reset complete."}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

