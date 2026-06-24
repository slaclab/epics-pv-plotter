app = FastAPI(lifespan=lifespan)

# FastAPI does this：
class FastAPI:
    def __init__(self, lifespan=None):
        self.lifespan = lifespan
    
    async def startup(self):
        """call it when the server starts"""
        if self.lifespan:
            # create context manager
            self.lifespan_context = self.lifespan(self)
            # call __aenter__() → execute to yield the code before yield
            await self.lifespan_context.__aenter__()
    
    async def shutdown(self):
        """call it when the server shuts down"""
        if self.lifespan_context:
            # call __aexit__() → execute the code after yield  
            await self.lifespan_context.__aexit__(None, None, None)
