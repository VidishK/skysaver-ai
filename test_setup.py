import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from google import genai

load_dotenv()

print("=" * 50)
print("SkySaver AI — Setup Smoke Test")
print("=" * 50)

# Test 1: MongoDB connection (with certifi for macOS SSL)
print("\n[1/2] Testing MongoDB connection...")
try:
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(
        mongo_uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
    )
    client.admin.command("ping")
    print("    PASS — MongoDB is reachable")
except Exception as e:
    print(f"    FAIL — {e}")

# Test 2: Gemini via Vertex AI (ADC)
print("\n[2/2] Testing Gemini via Vertex AI...")
try:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    gemini_client = genai.Client(vertexai=True, project=project, location=location)
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: SkySaver AI is live.",
    )
    print(f"    PASS — Gemini replied: {response.text.strip()}")
except Exception as e:
    print(f"    FAIL — {e}")

print("\n" + "=" * 50)
print("Smoke test complete.")
print("=" * 50)