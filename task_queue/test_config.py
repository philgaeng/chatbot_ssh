from config import redis_config, redis_url
import os

print("Environment variables:")
print(f"REDIS_PASSWORD from env: {os.getenv('REDIS_PASSWORD')}")
print("\nRedis Config:")
print(f"Host: {redis_config.host}")
print(f"Port: {redis_config.port}")
print(f"DB: {redis_config.db}")
print(f"Password: {redis_config.password}")
print(f"\nRedis URL: {redis_url}") 