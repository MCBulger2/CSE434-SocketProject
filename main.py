#!/usr/bin/python

import getopt
import sys

import client
import manager


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "m", ["manager"])
    except getopt.GetoptError:
        print
        "main.py -m"
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-m":
            manager.start_manager()

    client.start_client()


if __name__ == '__main__':
    main(sys.argv[1:])


