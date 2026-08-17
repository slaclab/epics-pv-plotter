#!/usr/bin/env python3
import asyncio
from caproto.asyncio.client import Context

PV = "SPEAR:BeamCurrAvg"  # Change this to a PV that updates periodically

'''
async for equals to 




_it = aiter(subscription)
while True:
    try:
        event = await anext(_it)   # to get the next element
    except StopAsyncIteration:
        break


'''


'''

async def main():
    ctx = Context()
    pv, = await ctx.get_pvs(PV)

    subscription = pv.subscribe(data_type="time")
    print("subscription type:", type(subscription))
    print("has __aiter__:", hasattr(subscription, "__aiter__"))

    n = 0
    async for event in subscription:
        n += 1
        print("\n=== EVENT", n, "===")
        print("event type:", type(event))
        print("dir(event):", [a for a in dir(event) if not a.startswith("_")])

        print("has data:", hasattr(event, "data"))
        print("has metadata:", hasattr(event, "metadata"))

        print("event.data type:", type(event.data))
        print("event.data repr:", repr(event.data))

        md = event.metadata
        print("metadata type:", type(md))
        print("dir(metadata):", [a for a in dir(md) if not a.startswith("_")])

        for k in ["timestamp", "status", "severity"]:
            if hasattr(md, k):
                print(f"metadata.{k} =", getattr(md, k))

        if n >= 1:
            break

    await subscription.clear()
    await ctx.disconnect()

'''
async def main():
    ctx = Context()
    pv, = await ctx.get_pvs(PV)

    subscription = pv.subscribe(data_type="time")
    print("subscription type:", type(subscription))
    print("has __aiter__:", hasattr(subscription, "__aiter__"))
    print("has __anext__:", hasattr(subscription, "__anext__"))

    async_iter = aiter(subscription)

    event1 = await anext(async_iter)
    print("event1:", event1)

    event2 = await anext(async_iter)
    print("event2:", event2)




if __name__ == "__main__":
    asyncio.run(main())
