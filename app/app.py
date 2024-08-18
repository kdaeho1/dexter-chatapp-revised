from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from config import Config
import os
from werkzeug.utils import secure_filename
from openai import OpenAI
from database import db
from models import User, Message, VoiceMessage

# Entry Point
app = Flask(__name__)  # Create a new Flask application instance
app.config.from_object(Config)  # Load configuration from the Config object

db.init_app(app)  # Initialize SQLAlchemy with the Flask app

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Create the upload folder if it doesn't exist

# Initialize OpenAI client
client = OpenAI()  # Initialize the OpenAI client for interacting with OpenAI APIs

with app.app_context():
    db.create_all()  # Create all database tables if they don't exist

# Route to create a new user
@app.route('/users', methods=['POST'])
def create_user():
    data = request.json  # Get JSON data from the request
    username = data.get('username')  # Extract the username from the data
    if not username:
        return jsonify({"error": "Username is required"}), 400  # Return an error if username is missing
    existing_user = User.query.filter_by(username=username).first()  # Check if the username already exists
    if existing_user:
        return jsonify({"error": "Username already exists"}), 409  # Return an error if the username is taken
    new_user = User(username=username)  # Create a new user object
    db.session.add(new_user)  # Add the new user to the database session
    db.session.commit()  # Commit the session to save the user in the database
    return jsonify({"id": new_user.id, "username": new_user.username}), 201  # Return the new user's info

# Route to get a list of all users
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()  # Query all users from the database
    return jsonify([{"id": user.id, "username": user.username} for user in users])  # Return user data as JSON

# Route to send a message between users
@app.route('/messages', methods=['POST'])
def send_message():
    data = request.json  # Get JSON data from the request
    sender_id = data.get('sender_id')  # Extract the sender ID
    recipient_id = data.get('recipient_id')  # Extract the recipient ID
    content = data.get('content')  # Extract the message content
    
    if not sender_id or not recipient_id or not content:
        return jsonify({"error": "sender_id, recipient_id, and content are required"}), 400  # Validate input
    elif len(content) > 10:
        return jsonify({"error": "message is longer than 500 characters"}), 401
    sender = User.query.get(sender_id)  # Get the sender from the database
    recipient = User.query.get(recipient_id)  # Get the recipient from the database
    if not sender or not recipient:
        return jsonify({"error": "Sender or recipient not found"}), 404  # Check if sender and recipient exist
    
    new_message = Message(content=content, sender_id=sender_id, recipient_id=recipient_id)  # Create a new message
    db.session.add(new_message)  # Add the message to the session
    db.session.commit()  # Commit the session to save the message in the database
    
    return jsonify({
        "id": new_message.id,
        "content": new_message.content,
        "timestamp": new_message.timestamp,
        "sender_id": new_message.sender_id,
        "recipient_id": new_message.recipient_id
    }), 201  # Return the new message details

# Route to get all messages between two users
@app.route('/messages', methods=['GET'])
def get_messages():
    user1_id = request.args.get('user1_id')  # Extract the first user ID from the query parameters
    user2_id = request.args.get('user2_id')  # Extract the second user ID from the query parameters
    
    if not user1_id or not user2_id:
        return jsonify({"error": "Both user1_id and user2_id are required"}), 400  # Validate input
    
    # Query messages where user1 is the sender and user2 is the recipient or vice versa
    messages = Message.query.filter(
        ((Message.sender_id == user1_id) & (Message.recipient_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.recipient_id == user1_id))
    ).order_by(Message.timestamp).all()  # Order by timestamp
    
    return jsonify([{
        "id": message.id,
        "content": message.content,
        "timestamp": message.timestamp,
        "sender_id": message.sender_id,
        "recipient_id": message.recipient_id
    } for message in messages])  # Return the messages as JSON

# Route to upload a voice message and get a transcription
@app.route('/voice_messages', methods=['POST'])
def upload_voice_message():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400  # Validate that a file was uploaded
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400  # Validate that a file was selected
    
    sender_id = request.form.get('sender_id')  # Extract the sender ID from the form data
    recipient_id = request.form.get('recipient_id')  # Extract the recipient ID from the form data
    
    if not sender_id or not recipient_id:
        return jsonify({"error": "sender_id and recipient_id are required"}), 400  # Validate input
    
    if file and file.filename.rsplit('.', 1)[1].lower() in ['wav', 'mp3', 'ogg']:  # Check file extension
        filename = secure_filename(file.filename)  # Secure the filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)  # Define the file path
        file.save(file_path)  # Save the file
        
        try:
            with open(file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)  # Transcribe
            transcription = transcript.text  # Extract the transcription text
        except Exception as e:
            transcription = f"Transcription failed: {str(e)}"  # Handle transcription errors
        
        # Create a new voice message with the transcription
        new_voice_message = VoiceMessage(
            filename=filename, 
            sender_id=sender_id, 
            recipient_id=recipient_id,
            transcription=transcription
        )
        
        db.session.add(new_voice_message)  # Add the voice message to the session
        db.session.commit()  # Commit the session to save the voice message in the database
        
        # Delete the audio file after transcription
        os.remove(file_path)
        
        return jsonify({
            "id": new_voice_message.id,
            "filename": new_voice_message.filename,
            "timestamp": new_voice_message.timestamp,
            "sender_id": new_voice_message.sender_id,
            "recipient_id": new_voice_message.recipient_id,
            "transcription": new_voice_message.transcription
        }), 201  # Return the voice message details
    return jsonify({"error": "File type not allowed. Only WAV, MP3, and OGG files are accepted."}), 400  # Invalid file

# Route to get all voice messages between two users
@app.route('/voice_messages', methods=['GET'])
def get_voice_messages():
    user1_id = request.args.get('user1_id')  # Extract the first user ID from the query parameters
    user2_id = request.args.get('user2_id')  # Extract the second user ID from the query parameters
    
    if not user1_id or not user2_id:
        return jsonify({"error": "Both user1_id and user2_id are required"}), 400  # Validate input
    
    # Query voice messages where user1 is the sender and user2 is the recipient or vice versa
    voice_messages = VoiceMessage.query.filter(
        ((VoiceMessage.sender_id == user1_id) & (VoiceMessage.recipient_id == user2_id)) |
        ((VoiceMessage.sender_id == user2_id) & (VoiceMessage.recipient_id == user1_id))
    ).order_by(VoiceMessage.timestamp).all()  # Order by timestamp
    
    return jsonify([{
        "id": vm.id,
        "filename": vm.filename,
        "timestamp": vm.timestamp,
        "sender_id": vm.sender_id,
        "recipient_id": vm.recipient_id,
        "transcription": vm.transcription
    } for vm in voice_messages])  # Return the voice messages as JSON

# Run the app in debug mode
if __name__ == '__main__':
    app.run(debug=True)
