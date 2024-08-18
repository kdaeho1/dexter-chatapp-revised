import requests
import json
import os
import configparser
from prettytable import PrettyTable
import time
import pyaudio
import wave
import tempfile

# Function to load configuration settings from a config file
def load_config(config_file='config.ini'):
    config = configparser.ConfigParser()  # Create a ConfigParser object
    config.read(config_file)  # Read the configuration file
    
    # Default configuration values
    defaults = {
        'Username': 'DefaultUser',
        'ServerIP': '127.0.0.1',
        'ServerPort': '5000',
        'Debug': 'false'
    }
    
    # Update defaults with values from the config file if they exist
    if 'DEFAULT' in config:
        for key in defaults:
            if key in config['DEFAULT']:
                defaults[key] = config['DEFAULT'][key]
    
    # Convert 'Debug' value to a boolean
    defaults['Debug'] = defaults['Debug'].lower() == 'true'
    
    return defaults

# Load the configuration settings
CONFIG = load_config()
API_URL = f"http://{CONFIG['ServerIP']}:{CONFIG['ServerPort']}"  # Base API URL
USERNAME = CONFIG['Username']  # User's username
DEBUG = CONFIG['Debug']  # Debug mode flag

# Function to clear the console screen
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')  # 'cls' for Windows, 'clear' for others

# Function to print the main menu
def print_menu():
    print(f"\n--- Messaging App Menu (Logged in as {USERNAME}) ---")
    print("1. Send Text Message")
    print("2. Send Voice Message")
    print("3. View Messages")
    print("4. List Users")
    print("5. Exit")

# Function to get the user ID by username
def get_user_id(username):
    try:
        response = requests.get(f"{API_URL}/users")  # Send a GET request to retrieve users
        response.raise_for_status()  # Raise an error for bad status codes
        users = response.json()  # Parse the response as JSON
        for user in users:
            if user['username'] == username:
                return user['id']  # Return the ID if the username matches
    except requests.RequestException as e:
        print(f"Error retrieving users: {e}")  # Print an error if the request fails
    return None

# Function to create a new user with the given username
def create_user(username):
    try:
        response = requests.post(f"{API_URL}/users", json={"username": username})  # Send a POST request to create a user
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()['id']  # Return the new user's ID
    except requests.RequestException as e:
        print(f"Error creating user: {e}")  # Print an error if the request fails
    return None

# Function to send a text message
def send_text_message(sender_id):
    recipient = input("Enter recipient's username: ")  # Prompt for the recipient's username
    content = input("Enter your message: ")  # Prompt for the message content

    recipient_id = get_user_id(recipient)  # Get the recipient's user ID
    if not recipient_id:
        print("Recipient not found.")
        return

    data = {"sender_id": sender_id, "recipient_id": recipient_id, "content": content}  # Prepare the message data

    try:
        if DEBUG:
            print(f"Sending payload: {json.dumps(data, indent=2)}")  # Print the data in debug mode
        response = requests.post(f"{API_URL}/messages", json=data)  # Send a POST request to send the message
        response.raise_for_status()  # Raise an error for bad status codes
        print("Message sent successfully!")
    except requests.RequestException as e:
        print(f"Error sending message: {e}")  # Print an error if the request fails
        if DEBUG:
            print(f"Response content: {response.content}")  # Print response content in debug mode

# Function to record audio and save it to a file
def record_audio(duration=5, output_file='temp_voice_message.wav'):
    CHUNK = 1024  # Audio chunk size
    FORMAT = pyaudio.paInt16  # Audio format
    CHANNELS = 1  # Number of channels (mono)
    RATE = 44100  # Sample rate

    p = pyaudio.PyAudio()  # Initialize PyAudio

    # Open a stream for recording
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print(f"Recording for {duration} seconds...")

    frames = []  # List to hold the recorded audio frames

    for i in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)  # Read a chunk of audio data
        frames.append(data)  # Append it to the list of frames

    print("Recording finished.")

    stream.stop_stream()  # Stop the audio stream
    stream.close()  # Close the stream
    p.terminate()  # Terminate PyAudio

    # Save the recorded audio to a WAV file
    wf = wave.open(output_file, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# Function to send a voice message
def send_voice_message(sender_id):
    recipient = input("Enter recipient's username: ")  # Prompt for the recipient's username
    
    temp_file = 'temp_voice_message.wav'  # Temporary file to store the recording
    record_audio(duration=5, output_file=temp_file)  # Record a 5-second voice message

    recipient_id = get_user_id(recipient)  # Get the recipient's user ID
    if not recipient_id:
        print("Recipient not found.")
        return

    data = {"sender_id": sender_id, "recipient_id": recipient_id}  # Prepare the data for the request

    try:
        with open(temp_file, 'rb') as file:
            files = {'file': ('voice_message.wav', file, 'audio/wav')}  # Prepare the file for upload
            if DEBUG:
                print(f"Sending payload: {json.dumps(data, indent=2)}")  # Print the data in debug mode
                print(f"Sending file: {temp_file}")
            response = requests.post(f"{API_URL}/voice_messages", data=data, files=files)  # Send the voice message
            response.raise_for_status()  # Raise an error for bad status codes
        print("Voice message sent and transcribed successfully!")
        print(f"Transcription: {response.json()['transcription']}")  # Print the transcription
    except requests.RequestException as e:
        print(f"Error sending voice message: {e}")  # Print an error if the request fails
        if DEBUG:
            print(f"Response content: {response.content}")  # Print response content in debug mode
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)  # Delete the temporary file

# Function to view text and voice messages between the logged-in user and another user
def view_messages(user_id):
    other_user = input("Enter username to view messages with: ")  # Prompt for the other user's username
    other_id = get_user_id(other_user)  # Get the other user's ID

    if not other_id:
        print("User not found.")
        return

    try:
        # Retrieve text messages
        response = requests.get(f"{API_URL}/messages?user1_id={user_id}&user2_id={other_id}")
        # Retrieve voice messages
        voice_response = requests.get(f"{API_URL}/voice_messages?user1_id={user_id}&user2_id={other_id}")
        
        response.raise_for_status()  # Raise an error for bad status codes
        voice_response.raise_for_status()  # Raise an error for bad status codes

        messages = response.json()  # Parse text messages as JSON
        voice_messages = voice_response.json()  # Parse voice messages as JSON
        
        all_messages = messages + voice_messages  # Combine all messages
        all_messages.sort(key=lambda x: x['timestamp'])  # Sort messages by timestamp

        # Create a table to display the messages
        table = PrettyTable()
        table.field_names = ["Timestamp", "Sender", "Content"]
        
        # Retrieve the list of users to resolve user IDs to usernames
        users_response = requests.get(f"{API_URL}/users")
        users_response.raise_for_status()
        users = users_response.json()

        # Add each message to the table
        for msg in all_messages:
            sender = next((u['username'] for u in users if u['id'] == msg['sender_id']), "Unknown")
            content = msg.get('content') or msg.get('transcription', 'Voice Message')
            table.add_row([msg['timestamp'], sender, content])
        
        print(table)  # Print the table
    except requests.RequestException as e:
        print(f"Error retrieving messages: {e}")  # Print an error if the request fails


# Function to list all users in the system
def list_users():
    try:
        response = requests.get(f"{API_URL}/users")  # Send a GET request to retrieve users
        response.raise_for_status()  # Raise an error for bad status codes
        users = response.json()  # Parse the response as JSON
        table = PrettyTable()
        table.field_names = ["ID", "Username"]
        for user in users:
            table.add_row([user['id'], user['username']])  # Add each user to the table
        print(table)  # Print the table
    except requests.RequestException as e:
        print(f"Error retrieving users: {e}")  # Print an error if the request fails

# Main function that runs the messaging app
def main():
    clear_screen()
    print("Welcome to the Messaging App!")
    print(f"Logged in as {USERNAME}")
    if DEBUG:
        print("Debug mode is ON")

    user_id = get_user_id(USERNAME)  # Get the logged-in user's ID
    if not user_id:
        print("User not found. Creating new user.")
        user_id = create_user(USERNAME)  # Create a new user if not found
        if not user_id:
            print("Failed to create user. Exiting.")
            return

    while True:
        print_menu()  # Display the main menu
        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            send_text_message(user_id)  # Send a text message
        elif choice == '2':
            send_voice_message(user_id)  # Send a voice message
        elif choice == '3':
            view_messages(user_id)  # View messages
        elif choice == '4':
            list_users()  # List all users
        elif choice == '5':
            print("Thank you for using the Messaging App. Goodbye!")
            break  # Exit the app
        else:
            print("Invalid choice. Please try again.")

        input("\nPress Enter to continue...")
        clear_screen()

if __name__ == "__main__":
    main()  # Run the main function