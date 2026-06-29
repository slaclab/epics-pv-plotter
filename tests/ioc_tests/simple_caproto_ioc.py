import logging
from caproto.server import PVGroup, pvproperty, run


class SimpleIOC(PVGroup):
    # constant float PV → MY:VALUE
    value = pvproperty(value=3.14, name='VALUE')


if __name__ == '__main__':
    # Enable logging so we can see what's happening
    logging.basicConfig(level=logging.INFO)

    ioc = SimpleIOC(prefix='MY:')
    print("PV list:", list(ioc.pvdb.keys()))   # Show registered PV names
    run(ioc.pvdb)
