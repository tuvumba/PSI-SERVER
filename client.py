import telnetlib
import time

import telnetlib
import time

def listenTN(connection):
	response = connection.read_until(b"\a\b")

	return response.decode()
	
def send_and_recieve(text, connection, addAB):
	if addAB == 'Y':
		text += '\a\b'
	text = text.encode()
	print("Sent: ", text)
	connection.write(text)
	print("Response: ", listenTN(connection))	

# Connect to the server
host = "localhost"
port = 10000  # Default Telnet port
tn = telnetlib.Telnet(host, port)

while True:
	text = input("Enter text to send:")
	add = input("Do you want to add \\a\\b? (Y, N)")
	send_and_recieve(text, tn, add)

# Close the connection
tn.close()
# Close the connection
tn.close()


