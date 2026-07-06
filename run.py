import uvicorn
from app import config

if __name__ == "__main__":
    print(f"Starting CodeGuardian AI server on {config.HOST}:{config.PORT}...")
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)
