import socket
import sys
from threading import Thread

# Config part of server
SERVER_MOVE = '102 MOVE\a\b'.encode()
SERVER_TURN_LEFT = '103 TURN LEFT\a\b'.encode()
SERVER_TURN_RIGHT = '104 TURN RIGHT\a\b'.encode()
SERVER_PICK_UP = '105 GET MESSAGE\a\b'.encode()
SERVER_LOGOUT = '106 LOGOUT\a\b'.encode()
SERVER_KEY_REQUEST = '107 KEY REQUEST\a\b'.encode()
SERVER_OK = '200 OK\a\b'.encode()
SERVER_LOGIN_FAILED = '300 LOGIN FAILED\a\b'.encode()
SERVER_SYNTAX_ERROR = '301 SYNTAX ERROR\a\b'.encode()
SERVER_LOGIC_ERROR = '302 LOGIC ERROR\a\b'.encode()
SERVER_KEY_OUT_OF_RANGE_ERROR = '303 KEY OUT OF RANGE\a\b'.encode()

CLIENT_RECHARGING = 'RECHARGING'
CLIENT_FULL_POWER = 'FULL POWER'
ENDED_COMMUNICATION = "this is it, I have ended the server communication already, just exit lol"

CLIENT_OK_OR_CHARGE_LENGTH = 12
CLIENT_USERNAME_LENGTH = 20
CLIENT_KEY_LENGTH = 5
CLIENT_CONFIRMATION_LENGTH = 7
CLIENT_MESSAGE_LENGTH = 100

SERVER_KEYS = [[23019, 32037], [32037, 29295], [18789, 13603], [16443, 29533], [18189, 21952]]
STUCK_ACTIONS = [SERVER_TURN_LEFT, SERVER_MOVE, SERVER_TURN_RIGHT, SERVER_MOVE]


def prepare_message(data):
    data = str(data)
    data += '\a\b'
    data = data.encode()
    return data


def calculate_ascii_sum(name):
    char_sum = 0
    for nameChar in name:
        char_sum += ord(nameChar)
    char_sum = (char_sum * 1000) % 65536
    return char_sum


def calculate_server_hash(name, key_id):
    return (calculate_ascii_sum(name) + SERVER_KEYS[key_id][0]) % 65536


def calculate_client_hash(name, key_id):
    return (calculate_ascii_sum(name) + SERVER_KEYS[key_id][1]) % 65536


def check_hashes(name, client_hash, key_id):
    return calculate_client_hash(name, key_id) == client_hash


def check_length(command, stage):
    max_length = 0
    if stage == 0:
        max_length = 18
    elif stage == 1:
        max_length = 2
    elif stage == 2:
        max_length = 5
    elif stage == 3:
        max_length = 10
    elif stage == 4:
        max_length = 98

    if len(command) > max_length:
        return False
    else:
        return True


class my_server:
    def __init__(self):
        self.listOfThreads = []

    def start_communication(self, active_socket):
        while True:
            # print("Awaiting connection!")
            active_connection, client_address = active_socket.accept()
            active_connection.settimeout(1)
            thread1 = Thread(target=self.thread_communicate, args=(active_socket, active_connection, client_address))
            thread1.start()
            self.listOfThreads.append(thread1)

    def thread_communicate(self, active_socket, active_connection, client_address):
        commands = []
        username = ''
        stage = 0
        client_key = 0
        ended_error = False
        recharging = False
        message = ''
        prev_command = SERVER_MOVE
        print("Connected from ", client_address)
        robot = Robot()

        try:
            while True:
                new_commands = self.capture_data(active_connection, stage)
                if new_commands == -1:
                    active_connection.sendall(SERVER_SYNTAX_ERROR)
                    active_connection.close()
                    ended_error = True
                    break
                new_commands = new_commands[:-1]

                if new_commands:
                    commands += new_commands
                    print("Current commands: ", commands, " len: ", len(commands))

                    if commands[0] == CLIENT_RECHARGING:
                        if not recharging:
                            active_connection.settimeout(5)
                            recharging = True
                            commands.pop(0)
                            continue
                        else:
                            active_connection.sendall(SERVER_LOGIC_ERROR)
                            active_connection.close()
                            ended_error = True
                            break
                    elif commands[0] == CLIENT_FULL_POWER:
                        if recharging:
                            active_connection.settimeout(1)
                            recharging = False
                            commands.pop(0)
                            continue
                        else:
                            active_connection.sendall(SERVER_LOGIC_ERROR)
                            active_connection.close()
                            ended_error = True
                            break

                    if recharging:
                        active_connection.sendall(SERVER_LOGIC_ERROR)
                        active_connection.close()
                        ended_error = True
                        break

                    while len(commands) > 0:
                        if stage == 0:
                            username = self.process_command(commands[0], stage, active_connection)
                            if username == ENDED_COMMUNICATION:
                                ended_error = True
                                break
                            print("got username: ", username)
                            stage += 1
                        elif stage == 1:
                            client_key = self.process_command(commands[0], stage, active_connection)
                            if client_key == ENDED_COMMUNICATION:
                                ended_error = True
                                break
                            else:
                                server_hash = calculate_server_hash(username, client_key)
                                active_connection.sendall(prepare_message(server_hash))
                                stage += 1
                        elif stage == 2:
                            client_hash = self.process_command(commands[0], stage, active_connection)
                            if client_hash == ENDED_COMMUNICATION:
                                ended_error = True
                                break
                            else:
                                client_hash = int(client_hash)
                                own_client_hash = calculate_client_hash(username, client_key)
                                print("our client hash: ", own_client_hash)
                                print("client hash: ", client_hash)
                                if client_hash != own_client_hash:
                                    print("S2 - BAD, sent SERVER_LOGIN_FAILED")
                                    active_connection.sendall(SERVER_LOGIN_FAILED)
                                    active_connection.close()
                                    ended_error = True
                                    break
                                else:
                                    print("S2 - OK, sent SERVER_OK")
                                    active_connection.sendall(SERVER_OK)
                                    active_connection.sendall(SERVER_MOVE)
                                    stage += 1
                        elif stage == 3:
                            ''' send out move(did in stage 2), then get move
                             don't change stage until 0-0  
                              if 0-0, send request pickup, change stage'''
                            tmp_x, tmp_y = self.process_command(commands[0], stage, active_connection)
                            next_command = robot.move(tmp_x, tmp_y, prev_command)
                            prev_command = next_command
                            active_connection.sendall(next_command)
                            print("SENT: ", next_command.decode())
                            robot.print()
                            if robot.arrived:
                                stage += 1

                        elif stage == 4:
                            message = self.process_command(commands[0], stage, active_connection)
                            if message == ENDED_COMMUNICATION:
                                ended_error = True
                                break
                            print("Ended successfully!")
                            print("Message: ", message)
                            active_connection.sendall(SERVER_LOGOUT)
                            active_connection.close()
                            return

                        if ended_error:
                            print("Server communication ended on error.")
                            break
                        else:
                            # print("deleted first command")
                            commands.pop(0)
                            print("new commands: ", commands, " len: ", len(commands))
                if ended_error:
                    break

        except socket.timeout:
            print("TIMEOUT!")
            active_connection.close()
            # don't forget to pop front commands

    def process_command(self, command, stage, connection):
        """STAGE, 0 = USERNAME, 1 = CLIENT_KEY_ID, 2 = CLIENT CONFIRM,
        3 = MOVING, 4 = MESSAGE"""
        print("PROCESSING GOT ", command, "STAGE: ", stage)
        if stage == 0:
            print("STAGE 0 PROCESSING")
            if len(command) > CLIENT_USERNAME_LENGTH - 2:
                print("S0 - LENGTH >")
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
                return ENDED_COMMUNICATION
            else:
                print("S0 - OK, sent key_request")
                connection.sendall(SERVER_KEY_REQUEST)
                return command  # don't forget to add stage if not ENDED
        elif stage == 1:
            if len(command) > CLIENT_KEY_LENGTH - 2:
                print("S1 - LENGTH >")
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
            elif command.isdigit():
                command = int(command)
                if command < 0 or command > 4:
                    print("S1 - Wrong key: ", command)
                    connection.sendall(SERVER_KEY_OUT_OF_RANGE_ERROR)
                    connection.close()
                    return ENDED_COMMUNICATION
                else:
                    print("S1 OK, KEY: ", command)
                    return command  # calculate hash, send server_conf
            else:
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
                return ENDED_COMMUNICATION
        elif stage == 2:
            if len(command) > CLIENT_CONFIRMATION_LENGTH - 2 or not command.isdigit():
                print("S2 LEN> or not digit")
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
                return ENDED_COMMUNICATION
            else:
                return int(command)  # check if hash is correct, respond
        elif stage == 3:
            if len(command) > CLIENT_OK_OR_CHARGE_LENGTH - 2:
                print("S3 LENGTH>")
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
                return ENDED_COMMUNICATION
            else:
                command = str(command)
                command = command.split(' ')
                if len(command) != 3 or command[0] != 'OK' \
                        or not command[1].lstrip('-').isdigit() \
                        or not command[2].lstrip('-').isdigit():
                    print("S3 WRONG SYNTAX")
                    connection.sendall(SERVER_SYNTAX_ERROR)
                    connection.close()
                    return ENDED_COMMUNICATION
                else:
                    print("S3 OK, X: ", command[1], ", Y: ", command[2])
                    return int(command[1]), int(command[2])  # returned coordinates
        elif stage == 4:
            if len(command) > CLIENT_MESSAGE_LENGTH - 2:
                print("S4 MESSAGE TOO LONG")
                connection.sendall(SERVER_SYNTAX_ERROR)
                connection.close()
                return ENDED_COMMUNICATION
            else:
                print("S4 OK, Closing Connection")
                connection.sendall(SERVER_LOGOUT)
                connection.close()
                return command  # got message, ended all

    def capture_data(self, active_connection, stage):

        data_raw = active_connection.recv(100)
        data_raw = data_raw.decode()
        if data_raw == '':
            return []
        print('Received1 {!r}'.format(data_raw))
        commands = data_raw.split('\x07\x08')
        last_command = commands[-1]
        print(commands)

        if check_length(last_command, stage):
            while last_command != '':
                data_new = active_connection.recv(100)
                data_new = data_new.decode()
                if data_new != '':
                    print('Received2 {!r}'.format(data_new))
                    data_raw += data_new
                    commands = data_raw.split('\x07\x08')
                    last_command = commands[-1]
        else:
            print("too long for this stage")
            return -1

        # print("got data")
        return commands


class Robot:
    def __init__(self):
        self.robot_x = 613613613
        self.robot_y = 613613613
        self.robot_dir = -1  # 0 - RIGHT, 1 - UP, 2 - LEFT, 3 - DOWN
        self.robot_goal_dir = -1
        self.prev_x = 613613613
        self.prev_y = 613613613
        self.arrived = False
        self.stuck = False
        self.stuck_counter = -1

    def find_own_direction(self):
        if self.robot_x == self.prev_x and self.robot_y == self.prev_y:
            print("find_own_dir: inconclusive direction")

        elif self.robot_y == self.prev_y:
            self.robot_dir = 0 if self.robot_x > self.prev_x else 2
        elif self.robot_x == self.prev_x:
            self.robot_dir = 1 if self.robot_y > self.prev_y else 3
        else:
            print("find_own_direction: logic error, moved two coords at the same time")
        # TODO exception

    def rotate(self, direction):  # -1 for right, 1 for left
        self.robot_dir += int(direction)
        self.robot_dir = self.robot_dir % 4
        print("Rotated ", 'right' if direction == -1 else 'left', ", dir: ", self.robot_dir)

    def set_goal_dir(self):  # first move along OY, then OX
        if not self.arrived:
            if self.robot_y != 0:
                self.robot_goal_dir = 1 if int(self.robot_y) < 0 else 3
            elif self.robot_x != 0:
                self.robot_goal_dir = 0 if int(self.robot_x) < 0 else 2

    def print(self):
        print("X: ", self.robot_x, ", Y: ", self.robot_y)
        print("PREV X: ", self.prev_x, ", Y: ", self.prev_y)
        print("DIRECTION: ", self.robot_dir)
        print("GOAL DIRECTION: ", self.robot_goal_dir)

    def move(self, new_x, new_y, prev_action):

        if new_x == 0 and new_y == 0:
            self.arrived = True
            return SERVER_PICK_UP

        if self.prev_x == 613613613:
            self.prev_x = new_x
            self.prev_y = new_y
            return SERVER_MOVE

        if self.robot_x == 613613613:
            self.robot_x = new_x
            self.robot_y = new_y
            self.find_own_direction()
            if self.robot_dir == -1:
                self.robot_x = 613613613
                if prev_action != SERVER_TURN_LEFT:
                    return SERVER_TURN_LEFT
                else:
                    return SERVER_MOVE
        else:
            self.prev_x = self.robot_x
            self.prev_y = self.robot_y
            self.robot_x = new_x
            self.robot_y = new_y

        if self.robot_x == self.prev_x and self.robot_y == self.prev_y and prev_action == SERVER_MOVE:
            self.stuck = True
            self.stuck_counter = 0
            return STUCK_ACTIONS[0]

        if self.stuck:

            self.stuck_counter += 1
            print("stuck count: ", self.stuck_counter)
            if self.stuck_counter == 3:
                self.stuck = False
                self.stuck_counter = 0
                return STUCK_ACTIONS[3]
            else:
                return STUCK_ACTIONS[self.stuck_counter]

        self.set_goal_dir()
        if self.robot_dir != self.robot_goal_dir:
            self.rotate(1)
            return SERVER_TURN_LEFT
        else:
            return SERVER_MOVE


def main():
    myServer = my_server()
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind the socket to the port
    server_address = ('localhost', 10000)
    print('starting up on {} port {}'.format(*server_address))
    mySocket.bind(server_address)

    # Listen for incoming connections
    mySocket.listen(1)
    # mySocket.setblocking(0)

    myServer.start_communication(mySocket)


if __name__ == "__main__":
    main()
