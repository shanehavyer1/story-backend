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
    # SECURITY: allows the frontend to talk to the backend from anywhere
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlayRequest(BaseModel):
    action: str

# --- 2. MEMORY SYSTEM (The Brain) ---
# The Journal: Summarizes the long-term past
game_summary = "The adventure begins. The player stands ready."
# Recent History: Keeps the exact text of the last few turns
recent_history = [] 

# --- 3. ROBUST MODEL SELECTOR (The Fix) ---
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
            print("DEBUG: No models found. Defaulting to Pro.")
            return genai.GenerativeModel("gemini-pro")

        # --- SELECTION LOGIC ---
        # 1. Try to find "gemini-1.5" (Newest/Best)
        for name in model_names:
            if "gemini-1.5" in name:
                return genai.GenerativeModel(name)
                
        # 2. Try to find "gemini-pro" (Standard)
        for name in model_names:
            if "gemini-pro" in name:
                return genai.GenerativeModel(name)

        # 3. Just grab the first one available
        return genai.GenerativeModel(model_names[0])

    except Exception as e:
        print(f"Model Selection Error: {e}")
        return genai.GenerativeModel("gemini-pro")

# --- 4. MEMORY SUMMARIZER ---
def update_summary(old_text):
    """
    Condenses old chat logs into the main journal so the game never crashes from being too long.
    """
    global game_summary
    try:
        model = get_best_available_model()
        prompt = (
            f"We are tracking a text adventure game.\n"
            f"CURRENT SUMMARY: {game_summary}\n"
            f"NEW EVENTS TO ADD: {old_text}\n"
            f"TASK: Rewrite the Current Summary to include the New Events. "
            f"Keep it concise (max 3 sentences). Focus on inventory, location, and major plot changes."
        )
        response = model.generate_content(prompt)
        if response.text:
            game_summary = response.text.strip()
            print(f"DEBUG: Memory Updated -> {game_summary}")
    except:
        pass

# --- 5. GAME ENDPOINTS ---
@app.post("/play")
async def play_turn(request: PlayRequest):
    global recent_history, game_summary
    
    # Create the prompt context (Journal + Recent Chat + New Action)
    recent_text = "\n".join(recent_history)
    prompt = (
        f"You are the Dungeon Master. \n"
        f"--- JOURNAL (Long Term Memory) ---\n{game_summary}\n"
        f"--- RECENT CHAT ---\n{recent_text}\n"
        f"PLAYER: {request.action}\n"
        f"INSTRUCTION: Narrate the result. React logically to the journal and conversation."
    )

    try:
        # Dynamically find the right tool for the job
        model = get_best_available_model()
        
        response = model.generate_content(prompt)
        story_text = response.text

        # Update Memory
        recent_history.append(f"Player: {request.action}")
        recent_history.append(f"DM: {story_text}")
        
        # Rolling Memory Buffer (Keep last 6 lines, summarize the rest)
        if len(recent_history) > 6:
            # Take the oldest 2 lines
            oldest_interaction = "\n".join(recent_history[:2])
            # Remove them from active list
            recent_history = recent_history[2:]
            # Send them to be summarized
            update_summary(oldest_interaction)

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
