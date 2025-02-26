import argparse
import helpers
import os
import re
import socket
import socketserver
import subprocess
import threading
import time
import unittest

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    dispatcher_server = None
    last_communication = 0
    busy = False
    dead = False

class TestHandler(socketserver.BaseRequestHandler):
    """
    The RequestHandler class for our test runner.
    """
    command_re = re.compile(r"(\w+)(:.+)*")
    BUF_SIZE = 1024

    def handle(self):
        # In Python 3, we need to decode bytes to string after receiving
        self.data = self.request.recv(self.BUF_SIZE).strip().decode("utf-8")
        command_groups = self.command_re.match(self.data)
        if not command_groups:
            # In Python 3, we need to encode strings to bytes before sending
            self.request.sendall("Invalid command".encode("utf-8"))
            return
        command = command_groups.group(1)
        if command == "ping":
            self.server.last_communication = time.time()
            self.request.sendall("pong".encode("utf-8"))
        elif command == "runtest":
            if self.server.busy:
                self.request.sendall("BUSY".encode("utf-8"))
            else:
                self.request.sendall("OK".encode("utf-8"))
                print("Running tests")
                self.server.busy = True
                commit_id = command_groups.group(2)[1:]
                self.run_tests(commit_id, self.server.repo)
                self.server.busy = False
    
    def run_tests(self, commit_id, repo):
        # Use universal_newlines=True to get string output instead of bytes
        output = subprocess.check_output(["./test_runner_script.sh", repo, commit_id], 
                                        universal_newlines=True)
        test_folder = os.path.join(repo, "tests")
        suite = unittest.TestLoader().discover(test_folder)
        # Specify encoding when opening files
        with open("results", "w", encoding="utf-8") as results_file:
            unittest.TextTestRunner(results_file).run(suite)
        
        with open("results", "r", encoding="utf-8") as f:
            output = f.read()
        # Use f-strings for string formatting
        helpers.communicate(self.server.dispatcher_server['host'],
                            int(self.server.dispatcher_server['port']),
                            f"results:{commit_id}:{len(output)}:{output}")

def dispatcher_checker(server):
    while not server.dead:
        time.sleep(5)
        if (time.time() - server.last_communication) > 10:
            try:
                print(f"Checking dispatcher status at {server.dispatcher_server['host']}:{server.dispatcher_server['port']}")
                response = helpers.communicate(
                    server.dispatcher_server['host'],
                    int(server.dispatcher_server['port']),
                    "status")
                print(f"Dispatcher status response: '{response}'")
                if response != "OK":
                    print(f"Unexpected response from dispatcher: '{response}' (expected 'OK')")
                    print("Test runner no longer functional, shutting down")
                    server.shutdown()
                    return
            except Exception as e:
                print(f"Exception while communicating with dispatcher: {type(e).__name__}: {e}")
                print("Can't communicate with test runner, shutting down")
                server.shutdown()
                return

def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatcher-server",
                    help="dispatcher host:port, " \
                    "by default it uses localhost:8888",
                    default="localhost:8888",
                    action="store")
    parser.add_argument("--host",
                    help="test runner's host, by default it uses localhost",
                    default="localhost",
                    action="store")
    parser.add_argument("--port",
                    help="test runner's port, by default it uses 8889",
                    default=8889,
                    action="store")
    parser.add_argument("repo", metavar="REPO", type=str,
                        help="repository to observe")
    args = parser.parse_args()
    dispatcher_host, dispatcher_port = args.dispatcher_server.split(":")
    server = ThreadedTCPServer((args.host, int(args.port)), TestHandler)
    # Use f-string for string formatting
    print(f'Serving on {args.host}:{int(args.port)}')
    server.dispatcher_server = {'host': dispatcher_host, 'port': dispatcher_port}
    server.repo = args.repo
    dispatcher_heartbeat = threading.Thread(target=dispatcher_checker, args=(server,))
    try:
        dispatcher_heartbeat.start()
        server.serve_forever()
    except (KeyboardInterrupt, Exception):
        server.dead = True
        dispatcher_heartbeat.join()

if __name__ == "__main__":
    serve()