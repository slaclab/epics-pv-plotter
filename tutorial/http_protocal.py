from fastapi import FastAPI

app = FastAPI()

# ================================================================
# HTTP GET request
# ================================================================
@app.get("/path")           # ← HTTP GET protocal
async def function():
    return {"data": "value"}

# ================================================================
# HTTP POST request
# ================================================================
@app.post("/path")          # ← HTTP POST protocal
async def function():
    return {"data": "value"}

# ================================================================
# HTTP PUT request
# ================================================================
@app.put("/path")           # ← HTTP PUT protocal
async def function():
    return {"data": "value"}

# ================================================================
# HTTP DELETE request
# ================================================================
@app.delete("/path")        # ← HTTP DELETE protocal
async def function():
    return {"data": "value"}

# ================================================================
# HTTP PATCH request
# ================================================================
@app.patch("/path")         # ← HTTP PATCH protocal
async def function():
    return {"data": "value"}

'''
HTTP Method	Purpose	    Operation	            Modifies Data	Idempotent	Safe	Example Use Case
GET	        Retrieve	Read/Query data	        ❌ No	        ✅ Yes	    ✅ Yes	View PV value
POST	    Create	    Submit/Create new data	✅ Yes	        ❌ No	    ❌ No	Add new record
PUT	        Replace	    Complete replacement	✅ Yes	        ✅ Yes	    ❌ No	Update entire PV config
PATCH	    Modify	    Partial update	        ✅ Yes	        ❌ No	    ❌ No	Modify specific field
DELETE	    Remove	    Delete resource	        ✅ Yes	        ✅ Yes	    ❌ No	Delete record
HEAD	    Metadata	Get headers only	    ❌ No	        ✅ Yes	    ✅ Yes	Check if resource exists
OPTIONS	    Discover	Get supported methods	❌ No	        ✅ Yes	    ✅ Yes	CORS preflight


CORS: Cross - Origin Resource Sharing
Environment<br> 	allow_origins	    allow_credentials	allow_methods	allow_headers	Security<br>
Development<br> 	["*"]	            True	            ["*"]	["*"]	⚠️ Low / 
Staging<br>         Specific list<br>	True	            Necessary<br>	Necessary<br>	⚙️ Medium /
Production<br>  	Specific list<br>	True	            Minimal<br>  	Minimal<br>  	✅ High / 

'''
