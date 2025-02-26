import argparse
import helpers
import os
import socket
import subprocess
import time

def update_repo(repo_path):
    """Python implementation of update_repo.sh functionality"""
    # Remove old commit ID file if it exists
    if os.path.exists(".commit_id"):
        os.remove(".commit_id")
        
    original_dir = os.getcwd()
    try:
        # Change to repo directory
        print(f"Checking repository: {repo_path}")
        os.chdir(repo_path)
        
        # Reset to HEAD
        print("Resetting to HEAD")
        subprocess.check_output(["git", "reset", "--hard", "HEAD"], universal_newlines=True)
        
        # Get current commit
        commit = subprocess.check_output(["git", "log", "-n1"], universal_newlines=True)
        commit_id = commit.split()[1]
        print(f"Current commit: {commit_id}")
        
        # Pull latest changes
        print("Pulling latest changes")
        subprocess.check_output(["git", "pull"], universal_newlines=True)
        
        # Get new commit
        new_commit = subprocess.check_output(["git", "log", "-n1"], universal_newlines=True)
        new_commit_id = new_commit.split()[1]
        print(f"New commit: {new_commit_id}")
        
        # If commit changed, write to file
        if new_commit_id != commit_id:
            print(f"Commit changed from {commit_id} to {new_commit_id}")
            os.chdir(original_dir)
            with open(".commit_id", "w", encoding="utf-8") as f:
                f.write(new_commit_id)
            return True
        else:
            print("No new commits")
            return False
    except Exception as e:
        print(f"Error updating repository: {e}")
        raise
    finally:
        # Ensure we return to original directory even if an error occurs
        os.chdir(original_dir)

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
    
    print(f"Starting repo observer for {args.repo}")
    print(f"Dispatcher server at {dispatcher_host}:{dispatcher_port}")
    
    while True:
        try:
            # Use our Python implementation instead of calling the bash script
            update_repo(args.repo)
            
            if os.path.isfile(".commit_id"):
                try:
                    print(f"Checking dispatcher status at {dispatcher_host}:{dispatcher_port}")
                    response = helpers.communicate(dispatcher_host,
                                                int(dispatcher_port),
                                                "status")
                    print(f"Dispatcher response: {response}")
                    
                    if response == "OK":
                        commit = ""
                        with open(".commit_id", "r", encoding="utf-8") as f:
                            commit = f.read().strip()
                        
                        print(f"Dispatching commit {commit}")
                        response = helpers.communicate(dispatcher_host,
                                                    int(dispatcher_port),
                                                    f"dispatch {commit}")
                        
                        if response != "OK":
                            print(f"Error from dispatcher: {response}")
                            raise Exception(f"Error while dispatching commit: {response}")
                        
                        print(f"Successfully dispatched commit {commit}")
                    else:
                        print(f"Dispatcher not ready: {response}")
                        raise Exception(f"Could not dispatch the test: {response}")
                except socket.error as e:
                    print(f"Socket error: {e}")
                    raise Exception(f"Error while communicating with dispatcher: {e}")
            else:
                print("No new commits to dispatch")
                
            print(f"Sleeping for 10 seconds before next check")
            time.sleep(10)
        except subprocess.CalledProcessError as e:
            print(f"Subprocess error: {e}")
            raise Exception(f"Error while polling repository: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise
        
if __name__ == "__main__":
    try:
        poll()
    except KeyboardInterrupt:
        print("Repository observer stopped by user")
    except Exception as e:
        print(f"Repository observer stopped due to error: {e}")