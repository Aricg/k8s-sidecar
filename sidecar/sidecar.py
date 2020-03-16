import os, logging, sys, socket, time, requests
from kubernetes import client, config

from resources import listResources, watchForChanges

def setup_custom_logger(name):
  formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
  handler = logging.FileHandler('log.txt', mode='w')
  handler.setFormatter(formatter)
  screen_handler = logging.StreamHandler(stream=sys.stdout)
  screen_handler.setFormatter(formatter)
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)
  logger.addHandler(screen_handler)
  return logger

def main():
  logger = setup_custom_logger('sidecar')
  if os.path.exists('/app/reload_successful.txt'):
    os.remove('/app/reload_successful.txt')
  with open('/app/reload_successful.txt', 'w', encoding='utf-8') as f:
    f.write("true")
  logger.info("Starting collector")
  folderAnnotation = os.getenv('FOLDER_ANNOTATIONS')
  if folderAnnotation is None:
    logger.info("No folder annotation was provided, defaulting to k8s-sidecar-target-directory")
    folderAnnotation = "k8s-sidecar-target-directory"

  label = os.getenv('LABEL')
  if label is None:
    logger.error("Should have added LABEL as environment variable! Exit")
    return -1

  targetFolder = os.getenv('FOLDER')
  if targetFolder is None:
    logger.error("Should have added FOLDER as environment variable! Exit")
    return -1

  resources = os.getenv('RESOURCE', 'configmap')
  resources = ("secret", "configmap") if resources == "both" else (resources, )
  logger.info("Selected resource type: %s" % resources)
  method = os.getenv('REQ_METHOD')
  url = os.getenv('REQ_URL')
  payload = os.getenv('REQ_PAYLOAD')
  config.load_incluster_config()
  logger.info("Config for cluster api loaded...")
  namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()

  if os.getenv('SKIP_TLS_VERIFY') == 'true':
    configuration = client.Configuration()
    configuration.verify_ssl = False
    configuration.debug = False
    client.Configuration.set_default(configuration)

  if os.getenv("METHOD") == "LIST":
    for res in resources:
      listResources(label, targetFolder, url, method, payload,
                    namespace, folderAnnotation, res, logger)
  else:
    host = '127.0.0.1'
    while True:
      r = requests.Session()
      try:
        http_code = r.get(url).status_code
        logger.debug("status_code is %d" % http_code)
        if (http_code == 405) or (http_code == 403):
          logger.info("Jenkins is contactable, continuing.")
          break
      except Exception:
        logger.info("Jenkins is not up yet.  Waiting...")
        time.sleep(5)

    watchForChanges(label, targetFolder, url, method,
                    payload, namespace, folderAnnotation, resources, logger)

if __name__ == '__main__':
  main()