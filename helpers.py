import socket

def communicate(host, port, message):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.sendall(message)
    response = s.recv(1024)
    s.close()
    return response