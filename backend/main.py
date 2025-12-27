import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from pydantic import BaseModel
import uvicorn

# --- 1. CONFIGURATION ---
# SECURITY: We look for the key in the server's environment variables first.
# If not found (running locally), we use your hardcoded key as a backup.
GEMINI_KEY = os.environ.get("GEMINI_KEY", "AIzaSyADlsZDZmZXPvOL95su2qjLN_3-NK7mzRo")
genai.configure(api_key=GEMINI_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    # SECURITY: In a real app, replace ["*"] with your specific frontend URL
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlayRequest(BaseModel):
    action: str

# --- 2. MEMORY SYSTEM ---
game_summary = "The adventure begins."
recent_history = [] 

def get_model():
    # ... (Same logic as before) ...
    return genai.GenerativeModel("gemini-1.5-flash")

def update_summary(old_text):
    global game_summary
    try:
        model = get_model()
        prompt = f"Summarize these events into the journal: {game_summary} \n New events: {old_text}"
        response = model.generate_content(prompt)
        game_summary = response.text.strip()
    except:
        pass

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
        model = get_model()
        response = model.generate_content(prompt)
        story_text = response.text

        recent_history.append(f"Player: {request.action}")
        recent_history.append(f"DM: {story_text}")

        if len(recent_history) > 6:
            update_summary("\n".join(recent_history[:2]))
            recent_history = recent_history[2:]

        return {"story": story_text}

    except Exception as e:
        return {"story": f"Error: {str(e)}"}

@app.post("/reset")
async def reset_game():
    global game_summary, recent_history
    game_summary = "The adventure begins."
    recent_history = []
    return {"message": "Reset complete."}

if __name__ == "__main__":
    # CLOUD CHANGE: The port must be read from the environment variable 'PORT'
    # The default is 8000 if not found.
    port = int(os.environ.get("PORT", 8000))
    # CLOUD CHANGE: Host must be 0.0.0.0 to work on the internet
    uvicorn.run(app, host="0.0.0.0", port=port)