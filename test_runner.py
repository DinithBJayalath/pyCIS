import argparse
import threading
import time
import helpers
import socket
import socketserver
import re
import subprocess
import os
import unittest

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    dispatcher_server = None
    last_communication = 0
    busy = False
    dead = False

class TestHandler(socketserver.BaseRequestHandler):
    """
    The RequestHandler class for our dispatcher.
    This will dispatch test runners against the incoming commit
    and handle their requests and test results
    """
    command_re = re.compile(r"(\w+)(:.+)*")
    BUF_SIZE = 1024

    def handle(self):
        self.data = self.request.recv(self.BUF_SIZE).strip()
        command_groups = self.command_re.match(self.data)
        if not command_groups:
            self.request.sendall("Invalid command")
            return
        command = command_groups.group(1)
        if command == "ping":
            self.server.last_communication = time.time()
            self.request.sendall("pong")
        elif command == "runtest":
            if self.server.busy:
                self.request.sendall("BUSY")
            else:
                self.request.sendall("OK")
                print("Running tests")
                self.server.busy = True
                commit_id = command_groups.group(2)[1:]
                self.run_tests(commit_id, self.server.repo)
                self.server.busy = False
    
    def run_tests(self, commit_id, repo):
        output = subprocess.check_output(["./test_runner_script.sh", repo, commit_id])
        test_folder = os.path.join(repo, "tests")
        suite = unittest.TestLoader().discover(test_folder)
        results_file = open("results", "w")
        unittest.TextTestRunner(results_file).run(suite)
        results_file.close()
        with open("results", "r") as f:
            output = f.read()
        helpers.communicate(self.server.dispatcher_server['host'],
                            int(self.server.dispatcher_server['port']),
                            "results:%s:%s:%s" % (commit_id, len(output), output))

def serve():
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
    server = ThreadedTCPServer((dispatcher_host, int(dispatcher_port)), TestHandler)
    print('Serving on %s:%s' % (dispatcher_host, int(dispatcher_port)))
    dispatcher_heartbeat = threading.Thread(target=dispatcher_checker, args=(server,))
    try:
        dispatcher_heartbeat.start()
        server.serve_forever()
    except (KeyboardInterrupt, Exception):
        server.dead = True
        dispatcher_heartbeat.join()
            
    def dispatcher_checker(server):
        while not server.dead:
            time.sleep(5)
            if (time.time() - server.last_communication) > 10:
                try:
                    response = helpers.communicate(
                        server.dispatcher_server['host'],
                        int(server.dispatcher_server['port']),
                        "status")
                    if response != "OK":
                        print("Test runner no longer functional, shutting down")
                        server.shutdown()
                        return
                except socket.error as e:
                    print("Can't communicate with test runner: %s" % e)
                    server.shutdown()
                    return