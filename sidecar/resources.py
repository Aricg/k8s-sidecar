import base64
import os
from multiprocessing import Process
from time import sleep

from kubernetes import client, watch
from kubernetes.client.rest import ApiException
from urllib3.exceptions import ProtocolError

from helpers import request, writeTextToFile, removeFile

_list_namespaced = {
    "secret": "list_namespaced_secret",
    "configmap": "list_namespaced_config_map"
}

_list_for_all_namespaces = {
    "secret": "list_secret_for_all_namespaces",
    "configmap": "list_config_map_for_all_namespaces"
}


def _get_file_data_and_name(full_filename, content, resource, logger):
    if resource == "secret":
        file_data = base64.b64decode(content).decode()
    else:
        file_data = content

    if full_filename.endswith(".url"):
        filename = full_filename[:-4]
        file_data = request(file_data, "GET", logger,).text
    else:
        filename = full_filename

    return filename, file_data


def listResources(label, targetFolder, url, method, payload, current, folderAnnotation, resource, logger):
    v1 = client.CoreV1Api()
    namespace = os.getenv("NAMESPACE", current)
    if namespace == "ALL":
        ret = getattr(v1, _list_for_all_namespaces[resource])()
    else:
        ret = getattr(v1, _list_namespaced[resource])(namespace=namespace)

    for sec in ret.items:
        destFolder = targetFolder
        metadata = sec.metadata
        if metadata.labels is None:
            continue
        logger.info("Working on %s: %s/%s" % (resource, metadata.namespace, metadata.name))
        if label in sec.metadata.labels.keys():
            logger.info("Found %s with label" % resource)
            if sec.metadata.annotations is not None:
                if folderAnnotation in sec.metadata.annotations.keys():
                    destFolder = sec.metadata.annotations[folderAnnotation]

            dataMap = sec.data
            if dataMap is None:
                logger.info("No data field in %s" % resource)
                continue

            if label in sec.metadata.labels.keys():
                for data_key in dataMap.keys():
                    filename, filedata = _get_file_data_and_name(data_key, dataMap[data_key],
                                                                 resource, logger)
                    writeTextToFile(destFolder, filename, filedata)

                    if url is not None:
                        request(url, method, logger, payload)


def _watch_resource_iterator(label, targetFolder, url, method, payload,
                             current, folderAnnotation, resource, logger):
    v1 = client.CoreV1Api()
    namespace = os.getenv("NAMESPACE", current)
    if namespace == "ALL":
        stream = watch.Watch().stream(getattr(v1, _list_for_all_namespaces[resource]))
    else:
        stream = watch.Watch().stream(getattr(v1, _list_namespaced[resource]), namespace=namespace)

    for event in stream:
        destFolder = targetFolder
        metadata = event['object'].metadata
        if metadata.labels is None:
            continue
        logger.info("Working on %s %s/%s" % (resource, metadata.namespace, metadata.name))
        if label in event['object'].metadata.labels.keys():
            logger.info("%s with label found" % resource)
            if event['object'].metadata.annotations is not None:
                if folderAnnotation in event['object'].metadata.annotations.keys():
                    destFolder = event['object'].metadata.annotations[folderAnnotation]
                    logger.info("Found a folder override annotation, placing the %s in: %s" % (resource, destFolder))
            dataMap = event['object'].data
            if dataMap is None:
                logger.info("%s does not have data." % resource)
                continue
            eventType = event['type']
            for data_key in dataMap.keys():
                logger.info("File in %s %s %s " % (resource, data_key, eventType))
                if (eventType == "ADDED") or (eventType == "MODIFIED"):
                    filename, filedata = _get_file_data_and_name(data_key, dataMap[data_key],
                                                                 resource, logger)
                    writeTextToFile(destFolder, filename, filedata)

                    if url is not None:
                        request(url, method, logger, payload)
                else:
                    filename = data_key[:-4] if data_key.endswith(".url") else data_key
                    removeFile(destFolder, filename, logger)
                    if url is not None:
                        request(url, method, logger, payload)


def _watch_resource_loop(logger, *args):
    while True:
        try:
            _watch_resource_iterator(*args)
        except ApiException as e:
            if e.status != 500:
                logger.error("ApiException when calling kubernetes: %s" % e)
            else:
                raise
        except ProtocolError as e:
            logger.error("ProtocolError when calling kubernetes: %s" % e)
        except Exception as e:
            logger.error("Received unknown exception: %s" % e)


def watchForChanges(label, targetFolder, url, method, payload,
                    current, folderAnnotation, resources, logger):

    firstProc = Process(target=_watch_resource_loop,
                        args=(logger, label, targetFolder, url, method, payload,
                              current, folderAnnotation, resources[0], logger)
                        )
    firstProc.start()

    if len(resources) == 2:
        secProc = Process(target=_watch_resource_loop,
                          args=(logger, label, targetFolder, url, method, payload,
                                current, folderAnnotation, resources[1], logger)
                          )
        secProc.start()

    while True:
        if not firstProc.is_alive():
            logger.info("Process for %s died. Stopping and exiting" % resources[0])
            if len(resources) == 2 and secProc.is_alive():
                secProc.terminate()
            elif len(resources) == 2:
                logger.info("Process for %s also died..." % resources[1])
            raise Exception("Loop died")

        if len(resources) == 2 and not secProc.is_alive():
            logger.info("Process for %s died. Stopping and exiting" % resources[1])
            if firstProc.is_alive():
                firstProc.terminate()
            else:
                pass
                logger.info("Process for %s also died..." % resources[0])
            raise Exception("Loop died")

        sleep(5)
