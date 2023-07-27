import os
import time
import logging
import socket
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# Twitch IRC server and credentials
SERVER = 'irc.twitch.tv' # Leave As Is
PORT = 6667 # Leave As Is
NICK = 'REPLACE ME' # Enter the name of the account you want send messages as
TOKEN = 'REPLACE ME' # Enter the oauth code for the above account including the oauth: part. (Get oauth code from here https://twitchapps.com/tmi/ )
CHANNEL = '#REPLACE ME' # Enter the channel you want the messages to be sent to starting with # (e.g. #d_tronics_uk)

# Path to the text file
FILE_PATH = r'REPLACE ME\SOMETEXTFILE.txt' # Replace this with the FULL path to the text file

# Track the content of the file
last_content = None
is_paused = False  # Flag to track if sending track titles is paused or not. Change to True to default to NOT sending track updates to chat (You WILL NEED to use !unpause to start sending track updates to chat if set to True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)


def read_file_content():
    """
    Read the content of the text file.
    """
    with open(FILE_PATH, 'r') as file:
        return file.read().strip()


def send_message(sock, message):
    """
    Send a message to the Twitch chat.
    """
    message = f'PRIVMSG {CHANNEL} :{message}\r\n'
    sock.send(bytes(message, 'utf-8'))
    logger.info(f'Sent message: {message}')


def parse_chat_message(response):
    """
    Parse the Twitch chat message and extract the username and content.
    """
    parts = response.split(":", 2)
    if len(parts) < 3:
        return None, None
    username = parts[1].split("!")[0]
    message = parts[2].strip()
    return username, message


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, sock, logger):
        super().__init__()
        self.sock = sock
        self.logger = logger

    def on_modified(self, event):
        global last_content
        if not event.is_directory and event.src_path == FILE_PATH and not is_paused:
            current_content = read_file_content()

            if current_content != last_content:
                last_content = current_content
                message = f"/me Now Playing: {current_content}"
                send_message(self.sock, message)
                self.logger.info(f'Posted {current_content} in the Twitch chat.')


if __name__ == '__main__':
    # Create a logger instance
    logger = logging.getLogger('TwitchBot')

    while True:
        try:
            # Connect to Twitch IRC server
            sock = socket.socket()
            sock.connect((SERVER, PORT))
            sock.send(f'PASS {TOKEN}\r\n'.encode())
            sock.send(f'NICK {NICK}\r\n'.encode())
            sock.send(f'JOIN {CHANNEL}\r\n'.encode())

            logger.info('Bot connected to Twitch chat.')

            # Set up the file change handler
            event_handler = FileChangeHandler(sock, logger)
            observer = Observer()
            observer.schedule(event_handler, path=os.path.dirname(FILE_PATH), recursive=False)
            observer.start()

            while True:
                # Receive messages from the Twitch chat
                response = sock.recv(2048).decode().strip()
                logger.info(f'Response received: {response}')

                if not response:
                    # Connection closed, attempt to reconnect
                    break

                if "PRIVMSG" in response:
                    username, message = parse_chat_message(response)
                    if message and message.startswith('!song'):
                        song_content = read_file_content()
                        if username:
                            send_message(sock, f"/me @{username}, Current Song is: {song_content}")
                        else:
                            send_message(sock, f"/me Current Song is: {song_content}")
                        logger.info(f'Sent song content: {song_content}')
                    elif message and message.startswith('!pause'):
                        is_paused = True
                        send_message(sock, f"/me Track title updates paused.")
                        logger.info('Track title updates paused.')
                    elif message and message.startswith('!unpause'):
                        is_paused = False
                        send_message(sock, f"/me Track title updates resumed.")
                        logger.info('Track title updates resumed.')

        except KeyboardInterrupt:
            logger.info('Script terminated by user.')
            break
        except Exception as e:
            logger.error(f'An error occurred: {str(e)}')
            time.sleep(5)  # Wait for 5 seconds before attempting to reconnect

        observer.stop()
        observer.join()
