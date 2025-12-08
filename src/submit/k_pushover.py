
import requests
import dotenv
import os

dotenv.load_dotenv()

def push(message: str, title: str = "Job Application Update", user_key: str="", api_token:str=""):
    """
    Send a push notification via Pushover.
    """
    # user_key =  os.getenv("PUSHOVER_USER")
    # api_token = os.getenv("PUSHOVER_API_TOKEN")
    if user_key is None or api_token is None:
        print("[pushover] Missing user_key or api_token. Skipping push notification.")
        return  

    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": api_token,
        "user": user_key,
        "title": title,
        "message": message
    }

    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        print("[pushover] Push notification sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"[pushover] Failed to send push notification: {e}"  )