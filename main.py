import flet as ft
import socket
import threading
import base64
import os
from io import BytesIO

class ChatApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Chat - Cliente e Servidor"
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.username = ""
        self.clients = []  # Lista de clientes conectados (modo servidor)
        self.page.scroll = 'auto'
        self.page.bgcolor = 'orange'
        
        # FilePicker já adicionado à página
        self.file_picker = ft.FilePicker(on_result=self.process_file)
        self.page.overlay.append(self.file_picker)
        
        # Interface
        self.name_input = ft.TextField(label="Digite seu nome", width=300, color= 'black', bgcolor= 'white')
        self.ip_input = ft.TextField(label="Digite o IP do Servidor", width=300, color= 'black', bgcolor= 'white')
        self.message_input = ft.TextField(label="Mensagem", width=300, bgcolor= ft.Colors.RED, color= ft.Colors.BLACK,)
        self.chat_display = ft.Column()
        self.host_button = ft.ElevatedButton("Host", on_click=self.start_server, bgcolor= 'black', color= 'white')
        self.client_button = ft.ElevatedButton("Cliente", on_click=self.start_client, bgcolor= 'black', color= 'white')
        self.send_button = ft.ElevatedButton("Enviar", on_click=self.send_message, disabled=True, bgcolor= 'white', color= 'black',)
        self.file_button = ft.ElevatedButton("Enviar Arquivo", on_click=self.send_file, disabled=True, bgcolor= 'white', color= 'black',)
        self.progress_bar = ft.ProgressBar(value=0)
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        
        
        self.page.add(
            self.name_input,
            self.ip_input,
            ft.Row([self.host_button, self.client_button], alignment= 'center'),
            self.chat_display,
            self.message_input,
            self.send_button,
            self.file_button,
            self.progress_bar
        )

    def start_server(self, e):
        self.username = self.name_input.value.strip() or "Servidor"
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("0.0.0.0", 12345))
        self.server_socket.listen(5)
        self.running = True
        self.chat_display.controls.append(ft.Text("Servidor iniciado. Aguardando conexões...", color="white"))
        self.page.update()
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        while self.running:
            client, addr = self.server_socket.accept()
            self.clients.append(client)
            self.send_button.disabled = False
            self.file_button.disabled = False
            self.chat_display.controls.append(ft.Text(f"Cliente conectado: {addr}", color="white"))
            self.page.update()
            threading.Thread(target=self.receive_messages, args=(client,), daemon=True).start()

    def start_client(self, e):
        self.username = self.name_input.value.strip() or "Cliente"
        server_ip = self.ip_input.value.strip()
        if not server_ip:
            self.chat_display.controls.append(ft.Text("Digite o IP do servidor!", color="white"))
            self.page.update()
            return
        
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((server_ip, 12345))
            self.running = True  # Importante para iniciar o loop de recebimento
            self.chat_display.controls.append(ft.Text("Conectado ao servidor!", color="white"))
            self.send_button.disabled = False
            self.file_button.disabled = False
            self.page.update()
            threading.Thread(target=self.receive_messages, args=(self.client_socket,), daemon=True).start()
        except Exception as ex:
            self.chat_display.controls.append(ft.Text(f"Erro ao conectar: {ex}", color="red"))
            self.page.update()

    def broadcast(self, message, sender_socket=None):
        """Envie a mensagem para todos os clientes conectados, exceto o emissor (se definido)."""
        # Se o servidor enviar uma mensagem (digitada na interface), sender_socket será None e envia para todos.
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.send(message.encode())
                except Exception as ex:
                    print(f"Erro ao enviar para cliente: {ex}")

    def receive_messages(self, conn):
        while self.running:
            try:
                message = conn.recv(65536).decode()
                if not message:
                    break
                
                # Se estivermos no modo servidor (self.server_socket existe), encaminha a mensagem para os outros clientes
                if self.server_socket is not None:
                    self.broadcast(message, sender_socket=conn)
                
                # Atualiza a interface de qualquer forma
                self.chat_display.controls.append(ft.Text(message, color="green", size=20))
                self.page.update()
            except Exception as ex:
                print(f"Erro ao receber mensagem: {ex}")
                break

    def send_message(self, e):
        message = self.message_input.value.strip()
        if message:
            full_message = f"{self.username}: {message}"
            # Se for servidor, envie a mensagem para todos os clientes; se for cliente, envie para o servidor
            if self.server_socket is not None:
                self.broadcast(full_message)
                self.chat_display.controls.append(ft.Text(full_message, color="green", size=20))
            elif self.client_socket:
                try:
                    self.client_socket.send(full_message.encode())
                    self.chat_display.controls.append(ft.Text(full_message, color="green", size=20))
                except Exception as ex:
                    self.chat_display.controls.append(ft.Text(f"Erro ao enviar mensagem: {ex}", color="red"))
            self.message_input.value = ""
            self.page.update()

    def send_file(self, e):
        self.file_picker.pick_files(allow_multiple=False)
        self.page.update()

    def process_file(self, e: ft.FilePickerResultEvent):
        if e.files:
            file_path = e.files[0].path
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as file:
                file_data = base64.b64encode(file.read()).decode()

            # Enviando a mensagem com o arquivo codificado
            file_message = f"FILE:{filename}::{file_data}"

            # Se for servidor, enviar para todos os clientes; se for cliente, enviar para o servidor
            if self.server_socket is not None:
                self.broadcast(file_message)
                self.chat_display.controls.append(ft.Text(f"{self.username} enviou o arquivo: {filename}", color="white"))
            elif self.client_socket:
                try:
                    self.client_socket.send(file_message.encode())
                    self.chat_display.controls.append(ft.Text(f"{self.username} enviou o arquivo: {filename}", color="white"))
                except Exception as ex:
                    self.chat_display.controls.append(ft.Text(f"Erro ao enviar arquivo: {ex}", color="red"))

            # Criando e escrevendo o arquivo no cliente
            try:
                # Decodificando os dados e salvando o arquivo
                file_data_decoded = base64.b64decode(file_data)
                with open(f"received_{filename}", "wb") as received_file:
                    received_file.write(file_data_decoded)
                self.chat_display.controls.append(ft.Text(f"Arquivo {filename} recebido e salvo com sucesso.", color="white"))
            except Exception as ex:
                self.chat_display.controls.append(ft.Text(f"Erro ao salvar o arquivo: {ex}", color="red"))

            # Atualizando a barra de progresso
            self.progress_bar.value = 1.0
            self.page.update()
            self.progress_bar.value = 0.0
            self.page.update()
            
        
        
def main(page: ft.Page):
    ChatApp(page)

ft.app(target=main)
