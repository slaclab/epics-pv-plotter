# Set EPICS environment variables for your network (192.168.22.x)

export EPICS_CA_ADDR_LIST="192.168.22.255"  # Broadcast for your subnet
export EPICS_CA_AUTO_ADDR_LIST=YES
export EPICS_PVA_ADDR_LIST="192.168.22.255"
export EPICS_PVA_AUTO_ADDR_LIST=YES

