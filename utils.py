
import logging


def log_request(clientAddr, request, response):
    logger = logging.getLogger()
    logger.debug(f"----- Request from {clientAddr[0]}:{clientAddr[1]} -----")
    logger.debug(f"\t Request: \'{request}\'")
    logger.debug(f"\t Response: \'{response}\'")
    logger.debug("----- End of Request -----")