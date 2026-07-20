# when execute：
uvicorn.run(app, host="0.0.0.0", port=8000)

# execution order within uvicorn ：
async def serve():
    # 1. bind the port, not connected
    server = await create_server(host, port)
    
    # 2. 🔥 call app.startup()
    await app.startup()
    # all the code before yield execution in lifespan
    # CA_CONTEXT created
    
    # 3. list to the connection
    await server.start_listening()
    
    # 4. process all the requests
    await handle_requests()
    
    # 5. receive signal to shut down（Ctrl+C）
    await server.stop_listening()
    
    # 6. 🔥 call app.shutdown()
    await app.shutdown()
    # then execute all the code after yield in lifespan
