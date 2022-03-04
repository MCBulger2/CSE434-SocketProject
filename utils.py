# Matthew Bulger
# CSE 434
# Dr. Syrotiuk
# Socket Project

import logging


# Log a request to the console (used by the manager process)
def log_request(clientAddr, request, response):
    logger = logging.getLogger()
    logger.debug(f"----- Request from {clientAddr[0]}:{clientAddr[1]} -----")
    logger.debug(f"\t Request: \'{request}\'")
    logger.debug(f"\t Response: \'{response}\'")
    logger.debug("----- End of Request -----")