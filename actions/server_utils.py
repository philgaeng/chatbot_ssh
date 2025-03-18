import socket
import requests
import json
from typing import Optional, Dict
import os

def get_local_ip() -> str:
    """
    Get the local IP address of the machine.
    """
    try:
        # Create a socket connection to an external server
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect but helps get the local IP
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error getting local IP: {str(e)}")
        return "127.0.0.1"

def get_public_ip() -> Optional[str]:
    """
    Get the public IP address of the server.
    """
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json()['ip']
    except Exception as e:
        print(f"Error getting public IP: {str(e)}")
        return None

def get_server_url(port: int = 5005, protocol: str = "http") -> Dict[str, str]:
    """
    Get both local and public server URLs.
    
    Args:
        port (int): The port number the server is running on
        protocol (str): The protocol to use (http or https)
        
    Returns:
        Dict[str, str]: Dictionary containing local and public URLs
    """
    local_ip = get_local_ip()
    public_ip = get_public_ip()
    
    urls = {
        "local": f"{protocol}://{local_ip}:{port}",
        "localhost": f"{protocol}://localhost:{port}",
        "127.0.0.1": f"{protocol}://127.0.0.1:{port}"
    }
    
    if public_ip:
        urls["public"] = f"{protocol}://{public_ip}:{port}"
    
    return urls

def save_server_urls(urls: Dict[str, str], filepath: str = "server_urls.json"):
    """
    Save server URLs to a JSON file.
    
    Args:
        urls (Dict[str, str]): Dictionary of server URLs
        filepath (str): Path to save the JSON file
    """
    try:
        with open(filepath, 'w') as f:
            json.dump(urls, f, indent=4)
        print(f"Server URLs saved to {filepath}")
    except Exception as e:
        print(f"Error saving server URLs: {str(e)}")

def load_server_urls(filepath: str = "server_urls.json") -> Optional[Dict[str, str]]:
    """
    Load server URLs from a JSON file.
    
    Args:
        filepath (str): Path to the JSON file
        
    Returns:
        Optional[Dict[str, str]]: Dictionary of server URLs if file exists, None otherwise
    """
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error loading server URLs: {str(e)}")
        return None

def main():
    # Example usage
    urls = get_server_url()
    print("Available server URLs:")
    for name, url in urls.items():
        print(f"{name}: {url}")
    
    # Save URLs to file
    save_server_urls(urls)
    
    # Load URLs from file
    loaded_urls = load_server_urls()
    if loaded_urls:
        print("\nLoaded URLs from file:")
        for name, url in loaded_urls.items():
            print(f"{name}: {url}")

if __name__ == "__main__":
    main() 