import asyncio

async def main():
    event = asyncio.Event()
    
    # Task 1: Waiter
    async def waiter():
        print("Waiter: Starting to wait...")
        await event.wait()  # ← Blocked here
        print("Waiter: Received signal, continuing execution")
    
    # Task 2: Trigger
    async def trigger():
        await asyncio.sleep(3)  # Wait for 3 seconds
        print("Trigger: Sending signal")
        event.set()  # ← Trigger the event
    
    # Run waiter only
    await waiter()

    # Run both tasks concurrently
    # await asyncio.gather(waiter(), trigger())

asyncio.run(main())
