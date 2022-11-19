import sys
import socket

# Creates server socket.
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def receiver_main():
    PORT = 5000
    SIZE = 1024
    FORMAT = "utf-8"
    
    hostname = socket.gethostname()
    HOST = socket.gethostbyname(hostname)

    for i, arg in enumerate(sys.argv):
        if (arg == "-p"):
            PORT = int(sys.argv[i + 1])
            print(f"PORT set to: {PORT}\n")

    server_address = (HOST, PORT)
    serverSocket.bind(server_address)
    print("Starting server at:", server_address)

    serverSocket.listen(5)
    print("Waiting for client to connect...\n")

    while True:
        connection, address = serverSocket.accept()
        print("Client connected from: ", address)

        while True:
            data = connection.recv(SIZE).decode(FORMAT)
            if not data:
                break

            print(f"{address[0]}: \"{data}\"\n")

            connection.send("Receiver ACK".encode(FORMAT))

        connection.close()
