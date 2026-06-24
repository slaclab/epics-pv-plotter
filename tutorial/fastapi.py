from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    name: str
    email: str
    age: int

@app.post("/users")
async def create_user(user: User):
    """Create a new user in the system"""
    return {"created": user}

# ✅ Automatic interactive documentation at /docs
# ✅ Try APIs directly in browser
# ✅ Documentation always matches code
# ✅ OpenAPI/Swagger JSON at /openapi.json
'''
Interactive Swagger UI at http://localhost:8000/docs
Beautiful ReDoc at http://localhost:8000/redoc
Machine-readable OpenAPI schema
Request/response examples
"Try it out" feature in browser

'''




