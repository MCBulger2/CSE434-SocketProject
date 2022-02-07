
import math

groupNumber = 7
portsAllocated = 5  # allocate 5 ports for manager


def get_next_port():
    global portsAllocated

    next_port = -1
    if groupNumber % 2 == 0:
        next_port = ((groupNumber/2)*1000)+1000 + portsAllocated
    else:
        next_port = (math.ceil(groupNumber / 2) * 1000) + 500

    max_port = -1
    if groupNumber % 2 == 0:
        max_port = ((groupNumber/2)*1000)+1499
    else:
        max_port = (math.ceil(groupNumber / 2) * 1000) + 999

    if next_port > max_port:
        print("Out of ports")
        exit(1)

    portsAllocated += 1
    return next_port

