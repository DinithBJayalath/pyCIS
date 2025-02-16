import argparse
import subprocess
import os
import socket
import helpers
import time

def poll():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatcher-server",
                        help="dispatcher host:port, " \
                        "by default it uses localhost:8888",
                        default="localhost:8888",
                        action="store")
    parser.add_argument("repo", metavar="REPO", type=str,
                        help="repository to observe")
    args = parser.parse_args()
    dispatcher_host, dispatcher_port = args.dispatcher_server.split(":")
    while True:
        try:
            subprocess.check_output(["./update_repo.sh", args.repo])
            if os.path.isfile(".commit_id"):
                try:
                    response = helpers.communicate(dispatcher_host,
                                                   int(dispatcher_port),
                                                   "status")
                except socket.error as e:
                    raise Exception("Error while communicating with dispatcher: %s" % e)
                if response == "OK":
                    commit = ""
                    with open(".commit_id") as f:
                        commit = f.read().strip()
                    response = helpers.communicate(dispatcher_host,
                                                   int(dispatcher_port),
                                                   "dispatch %s" % commit)
                    if response != "OK":
                        raise Exception("Error while dispatching commit: %s" % response)
                    print("Dispatched commit %s" % commit)
                else:
                    raise Exception("Could not dispatch the test: %s" % response)
            time.sleep(10)
        except subprocess.CalledProcessError as e:
            raise Exception("Error while polling repository: %s" % e)