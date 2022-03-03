#!/usr/bin/python

import getopt
import sys
import logging

import client
import manager


# Entry point for application
# Parses the command line arguments (if any):
#   -m or --manager: start up as the manager process. If this is omitted (default), process will start as a client.
#   -v or --verbose: whether a client or manager, log more information to the console -- TODO
def main(argv):
    # Set up the logger with the proper format and level of verbosity
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    try:
        # Attempt to parse the command line arguments
        opts, args = getopt.getopt(argv, "mvq", ["manager", "verbose", "query"])
    except getopt.GetoptError:
        # If parsing was unsuccessful, show the proper usage and exit
        print("main.py [-m|-q] -v")
        sys.exit(2)

    # Take the appropriate action for each command line argument
    for opt, arg in opts:
        if opt == "-m":
            manager.start_manager()
            return
        if opt == "-q":
            try:
                client.query_manager()
            except KeyboardInterrupt:
            	print("Shutting down the client...")
            return

    # If not a manager, start up as a client process
    client.start_client()


if __name__ == '__main__':
    main(sys.argv[1:])


