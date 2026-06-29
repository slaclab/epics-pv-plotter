import asyncio
from p4p.nt import NTScalar
from p4p.server import Server
from p4p.server.asyncio import SharedPV


class SimpleIOC:
    def __init__(self, prefix="MY:"):
        self.prefix = prefix

    def build(self):
        # A constant float PV, initial value 3.14
        pv = SharedPV(nt=NTScalar('d'), initial=3.14)
        return {self.prefix + 'VALUE': pv}

    async def run(self):
        with Server(providers=[self.build()]):
            await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(SimpleIOC().run())
    except KeyboardInterrupt:
        pass
