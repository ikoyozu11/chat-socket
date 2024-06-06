import socket
import threading
import os

BUFFER_SIZE = 24 * 1024 * 1024

clients = {}
clients_lock = threading.Lock()

def handle_client(client_socket, username):
    try:
        while True:
            message = client_socket.recv(1024)
            if not message:
                break

            if message.startswith(b"file:"):
                _, recipient, filename = message.decode().split(":", 2)
                with clients_lock:
                    if recipient in clients:
                        clients[recipient].send(f"file:{username}:{filename}".encode())
                        threading.Thread(target=receive_file, args=(client_socket, clients[recipient], filename)).start()
                    else:
                        client_socket.send(f"User {recipient} not found.".encode())
            else:
                try:
                    decoded_message = message.decode()
                    if decoded_message.startswith("unicast:"):
                        _, recipient, msg = decoded_message.split(":", 2)
                        with clients_lock:
                            if recipient in clients:
                                clients[recipient].send(f"Unicast from {username}: {msg}".encode())
                            else:
                                client_socket.send(f"User {recipient} not found.".encode())
                    elif decoded_message.startswith("multicast:"):
                        _, recipients, msg = decoded_message.split(":", 2)
                        recipient_list = recipients.split(",")
                        with clients_lock:
                            for recipient in recipient_list:
                                if recipient in clients:
                                    clients[recipient].send(f"Multicast from {username}: {msg}".encode())
                                else:
                                    client_socket.send(f"User {recipient} not found.".encode())
                    elif decoded_message.startswith("broadcast:"):
                        _, msg = decoded_message.split(":", 1)
                        broadcast(msg, client_socket, username)
                    else:
                        print(f"Received from {username}: {decoded_message}")
                        broadcast(decoded_message, client_socket, username)
                except UnicodeDecodeError:
                    print(f"Binary data received from {username}")
    except Exception as e:
        print(f"Error handling client {username}: {e}")

    finally:
        with clients_lock:
            clients.pop(username, None)
        client_socket.close()

def broadcast(message, sender_socket, username):
    with clients_lock:
        for client in clients.values():
            if client != sender_socket:
                try:
                    client.send(f"\nBroadcast from {username}: {message}".encode())
                except Exception as e:
                    print(f"Error broadcasting message: {e}")
                    client.close()
                    clients.pop(client, None)

def receive_file(sender_socket, recipient_socket, filename):
    try:
        with open(f"received_{os.path.basename(filename)}", 'wb') as file:
            while True:
                data = sender_socket.recv(BUFFER_SIZE)
                if data == b"FILE_TRANSFER_COMPLETE":
                    print(f"File transfer complete: {filename}")
                    recipient_socket.send(f"Received file: {filename}".encode())
                    break
                if not data:
                    break
                file.write(data)
    except Exception as e:
        print(f"Error receiving file {filename}: {e}")
    finally:
        try:
            sender_socket.send(b"FILE_TRANSFER_COMPLETE")
        except:
            pass

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 11005))
    server.listen(5)
    print("Server started on port 11005")

    try:
        while True:
            client_socket, client_address = server.accept()
            print(f"Connection from {client_address}")

            username = client_socket.recv(1024).decode()
            with clients_lock:
                if username in clients:
                    client_socket.send("Username already taken. Disconnecting.".encode())
                    client_socket.close()
                else:
                    clients[username] = client_socket
                    client_socket.send("Welcome to the chat server!".encode())
                    threading.Thread(target=handle_client, args=(client_socket, username)).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()