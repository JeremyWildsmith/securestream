import sys
import socket
import os

clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def sender_main():
    PORT = 5000
    SIZE = 1024
    FORMAT = "utf-8"
    
    file_or_key = False
    file_name = None

    data = None

    hostname = socket.gethostname()
    HOST = socket.gethostbyname(hostname)

    for i, arg in enumerate(sys.argv):
        if (arg == "-p"):                         
            PORT = int(sys.argv[i + 1])
            print(f"Sending to PORT: {PORT}\n")
        elif (arg == "-s"):                        
            HOST = sys.argv[i + 1]
            print(f"Sending to IP Address: {HOST}\n")
        elif (arg == "-f"):
            file_or_key = True
            file_name = sys.argv[i + 1]
            print(f"File to send: {file_name}")
            file_exists = os.path.exists(file_name)
            if (file_exists):
                file_or_key = True
            else:
                print(f"File: {file_name} does not exist. Please check again.")
                exit()



    server_address = (HOST, PORT)
    
    clientSocket.connect(server_address)
    print("Connected to: ", server_address)

    if (file_or_key):
        file_exists = os.path.exists(file_name)

        if (file_exists):
            file = open(f"./{file_name}", "r")

            message = file.read()
            clientSocket.send(message.encode(FORMAT))
            
            data = clientSocket.recv(SIZE).decode(FORMAT)

            print(data)
            
            file.close()

    else:
        print("Enter a message to send:")
        message = input()

        clientSocket.send(message.encode(FORMAT))
        
        data = clientSocket.recv(SIZE).decode(FORMAT)

        while (data is None):
            # time.sleep(0.5)
            print("DATA DOESN'T EXIST, NEED TO RESEND")
            clientSocket.send(message.encode(FORMAT))

        if (data is not None):
            print("DATA EXISTS!")
            
        print(data)

    clientSocket.close()
