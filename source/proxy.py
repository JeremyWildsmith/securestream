import socket
import os
import sys
import random

proxyFromSender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

proxyToReceiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def main():
    RECV_PORT = 5001
    SEND_PORT = 5000
    SIZE = 1024
    FORMAT = "utf-8"

    packet_drop_rate = 0
    packet_drop_bool = True
    ack_drop_rate = 0
    ack_drop_bool = True

    hostname = socket.gethostname()
    PROXY_HOST = socket.gethostbyname(hostname)

    SERVER_HOST = None

    for i, arg in enumerate(sys.argv):

        if (arg == "-ps"):                         
            SEND_PORT = int(sys.argv[i + 1])
            print(f"Sending to PORT: {SEND_PORT}\n")
        elif (arg == "-pr"):
            RECV_PORT = int(sys.argv[i + 1])
            print(f"Receiving at PORT: {RECV_PORT}\n")
        elif (arg == "-s"):                        
            SERVER_HOST = sys.argv[i + 1]
            print(f"Sending to IP Address: {SERVER_HOST}\n")
        elif (arg == "-pd"):
            packet_drop_rate = float(sys.argv[i + 1])
            print(f"Packet drop rate set to: {packet_drop_rate}%")
        elif (arg == "-ad"):
            ack_drop_rate = float(sys.argv[i + 1])
            print(f"ACK drop rate set to: {ack_drop_rate}%")

    if (SERVER_HOST == None):
        print("Error: Receiver address not specified.")
    else:
        client_address = (PROXY_HOST, RECV_PORT)

        proxyFromSender.bind(client_address)
        print("Starting proxy at:", client_address)

        proxyFromSender.listen(1)
        print("Waiting for client to connect...\n")

        while True:
            connection, address = proxyFromSender.accept()
            print("Client connected from: ", address)

            while True:
                data = connection.recv(SIZE).decode(FORMAT)

                while (packet_drop_bool):
                    if random.randint(0, 100) > packet_drop_rate:
                        server_address = (SERVER_HOST, SEND_PORT)

                        proxyToReceiver.connect(server_address)
                        print("Connected to server: ", server_address)

                        proxyToReceiver.send(data.encode(FORMAT))
                        print("Data from sender sent to receiver")
                        packet_drop_bool = False
                    else:
                        data = None
                        print("packet from sender dropped!")
                        data = connection.recv(SIZE).decode(FORMAT)

                server_ack = proxyToReceiver.recv(SIZE).decode(FORMAT)
                
                if random.randint(0, 100) > ack_drop_rate:
                    connection.send(server_ack.encode(FORMAT))
                    print("ACK from receiver sent to client")
                else:
                    print("ACK from receiver dropped!")
                
                proxyFromSender.close()

    proxyToReceiver.close()
        

if __name__ == "__main__":
    main()