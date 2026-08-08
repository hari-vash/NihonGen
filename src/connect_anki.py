import json
import urllib.request

def request_anki(action: str, params: dict = None) -> dict:
    """
    Sends an HTTP POST request to the local AnkiConnect server.
    """
    if params is None:
        params = {}

    payload = {
        "action": action,
        "version": 6,
        "params": params
    }

    request = urllib.request.Request(
        url='http://localhost:8765', 
        data=json.dumps(payload).encode('utf-8')
    )

    try:
        response = urllib.request.urlopen(request)
        response_data = json.loads(response.read())
 
        if response_data.get('error'):
            raise Exception(f"AnkiConnect Error: {response_data['error']}")
            
        return response_data.get('result')
        
    except urllib.error.URLError:
        raise Exception("Failed to connect! Is Anki open and running on your computer?")