#!/usr/bin/env python3
import asyncio

class MyAsyncIterable:
    def __init__(self, values, name="sub"):
        self.values = list(values)
        self.name = name

    def __aiter__(self):
        print(f"{self.name}.__aiter__() called")
        return MyAsyncIterator(self.values, name=f"{self.name}.it")

class MyAsyncIterator:
    def __init__(self, values, name="it"):
        self.values = list(values)
        self.i = 0
        self.name = name

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i >= len(self.values):
            raise StopAsyncIteration
        v = self.values[self.i]
        print(f"{self.name}.__anext__() -> {v}")
        self.i += 1
        await asyncio.sleep(0)
        return v


async def demo_skip_bug():
    print("\n=== demo_skip_bug (mixing async for + anext on same iterator) ===")
    sub = MyAsyncIterable([10, 11, 12, 13, 14, 15], name="sub_skip")
    it = aiter(sub)

    print("\n-- WRONG: async for event in it + anext(it) inside loop --")
    async for event in it:
        print("async for got:", event)

        try:
            extra = await anext(it)
            print("manual anext got:", extra)
        except StopAsyncIteration:
            print("manual anext: StopAsyncIteration")
            break


async def demo_equivalence_manual_vs_asyncfor():
    print("\n=== demo_equivalence (manual loop vs async for) ===")

    # Manual loop: aiter(obj) + repeatedly anext(it)
    obj = MyAsyncIterable([1, 2, 3, 4], name="obj_manual")
    print("\n-- manual: it = aiter(obj); while True: x = await anext(it) --")
    it = aiter(obj)
    manual = []
    while True:
        try:
            x = await anext(it)
        except StopAsyncIteration:
            break
        manual.append(x)
    print("manual collected:", manual)

    # async for: async for x in obj
    obj = MyAsyncIterable([1, 2, 3, 4], name="obj_asyncfor")
    print("\n-- async for x in obj --")
    asyncfor_vals = []
    async for x in obj:
        asyncfor_vals.append(x)
    print("async for collected:", asyncfor_vals)

    print("\nSame result?", manual == asyncfor_vals)


async def demo_skip_visible():
    print("\n=== demo_skip_visible (events are skipped for the async for variable) ===")
    sub = MyAsyncIterable([10, 11, 12, 13, 14, 15], name="sub_visible")
    it = aiter(sub)

    print("\n-- WRONG pattern: discard one item via anext(it) each iteration --")
    processed = []
    async for event in it:
        # Consume and discard the next item (bug)
        try:
            await anext(it)
        except StopAsyncIteration:
            pass
        processed.append(event)

    print("processed (from async for variable only):", processed)
    print("expected if no bug:", [10, 11, 12, 13, 14, 15])


async def main():
    await demo_skip_bug()
    await demo_equivalence_manual_vs_asyncfor()
    await demo_skip_visible()

if __name__ == "__main__":
    asyncio.run(main())
