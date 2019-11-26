import os
import errno

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


def writeTextToFile(folder, filename, data):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    with open(folder + "/" + filename, 'w') as f:
        f.write(data)
        f.close()


def removeFile(folder, filename, logger):
    completeFile = folder + "/" + filename
    if os.path.isfile(completeFile):
        os.remove(completeFile)
    else:
        logger.error(f"Error: %s file not found" % completeFile)


def request(url, method, logger, payload=None):
    retryTotal = 5 if os.getenv('REQ_RETRY_TOTAL') is None else int(os.getenv('REQ_RETRY_TOTAL'))
    retryConnect = 5 if os.getenv('REQ_RETRY_CONNECT') is None else int(
        os.getenv('REQ_RETRY_CONNECT'))
    retryRead = 5 if os.getenv('REQ_RETRY_READ') is None else int(os.getenv('REQ_RETRY_READ'))
    retryBackoffFactor = 0.2 if os.getenv('REQ_RETRY_BACKOFF_FACTOR') is None else float(
        os.getenv('REQ_RETRY_BACKOFF_FACTOR'))
    timeout = 30 if os.getenv('REQ_TIMEOUT') is None else float(os.getenv('REQ_TIMEOUT'))

    r = requests.Session()
    retries = Retry(total=retryTotal,
                    connect=retryConnect,
                    read=retryRead,
                    backoff_factor=retryBackoffFactor,
                    status_forcelist=[500, 502, 503, 504])
    r.mount('http://', HTTPAdapter(max_retries=retries))
    r.mount('https://', HTTPAdapter(max_retries=retries))
    if url is None:
        logger.info("No url provided. Doing nothing.")
        return

    # If method is not provided use GET as default
    if method == "GET" or not method:
        res = r.get("%s" % url, timeout=timeout)
    elif method == "POST":
        res = r.post("%s" % url, json=payload, timeout=timeout)
        if res.status_code == 200:
            logger.info("%s request successfully sent to %s.  Response: %s %s" % (method, url, res.status_code, res.reason))
            with open('/app/reload_successful.txt', 'w', encoding='utf-8') as f:
                f.write("true")
        else:
            logger.error("%s request failed to send to %s.  Response: %s %s" % (method, url, res.status_code, res.reason))
            with open('/app/reload_successful.txt', 'w', encoding='utf-8') as f:
                f.write("false")
    return res
