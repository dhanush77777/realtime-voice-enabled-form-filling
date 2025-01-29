# import os
# import queue
# import threading
# import json
# from flask import Flask, render_template, request, jsonify
# from google.cloud import speech, texttospeech
# import pyaudio
# from anthropic import AnthropicVertex

# # Flask app setup
# app = Flask(__name__)

# # Google API Credentials
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "creds.json"

# # Audio Configurations
# RATE = 16000
# CHUNK = int(RATE / 10)
# audio_queue = queue.Queue()

# # Initialize Google Clients
# stt_client = speech.SpeechClient()
# tts_client = texttospeech.TextToSpeechClient()

# streaming_config = speech.StreamingRecognitionConfig(
#     config=speech.RecognitionConfig(
#         encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
#         sample_rate_hertz=RATE,
#         language_code="en-US",
#     ),
#     interim_results=False
# )

# # Initialize Anthropic's Claude via Vertex AI
# LOCATION = "us-east5"
# client = AnthropicVertex(region=LOCATION, project_id="alan-suite")

# # Registration Form Fields
# form_fields = [
#     {"field": "full name", "prompt": "What is your full name?"},
#     {"field": "email", "prompt": "What is your email address?"},
#     {"field": "phone number", "prompt": "What is your phone number?"},
#     {"field": "address", "prompt": "What is your full address?"},
#     {"field": "dob", "prompt": "What is your date of birth?"}
# ]
# form_data = {}
# current_field_index = 0


# class MicrophoneStream:
#     def __init__(self, rate, chunk):
#         self.rate = rate
#         self.chunk = chunk
#         self._audio_interface = pyaudio.PyAudio()
#         self._audio_stream = self._audio_interface.open(
#             format=pyaudio.paInt16,
#             channels=1, rate=self.rate, input=True, frames_per_buffer=self.chunk,
#             stream_callback=self._fill_buffer,
#         )
#         self._closed = False

#     def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
#         if in_data:
#             audio_queue.put(in_data)
#         return None, pyaudio.paContinue

#     def __enter__(self):
#         return self

#     def __exit__(self, type, value, traceback):
#         self._audio_stream.stop_stream()
#         self._audio_stream.close()
#         self._audio_interface.terminate()
#         self._closed = True

#     def generator(self):
#         while not self._closed:
#             chunk = audio_queue.get()
#             if chunk is None:
#                 return
#             data = [chunk]

#             while True:
#                 try:
#                     chunk = audio_queue.get(block=False)
#                     if chunk is None:
#                         return
#                     data.append(chunk)
#                 except queue.Empty:
#                     break

#             yield b"".join(data)


# def synthesize_speech(text):
#     """Convert text to speech using Google TTS."""
#     synthesis_input = texttospeech.SynthesisInput(text=text)
#     voice = texttospeech.VoiceSelectionParams(
#         language_code="en-US",
#         ssml_gender=texttospeech.SsmlVoiceGender.MALE
#     )
#     audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

#     try:
#         response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
#         filename = "response.wav"

#         if response.audio_content:
#             with open(filename, "wb") as out:
#                 out.write(response.audio_content)

#             os.system(f"ffplay -nodisp -autoexit {filename} > /dev/null 2>&1")

#             if os.path.exists(filename):
#                 os.remove(filename)
#         else:
#             print("❌ Google TTS returned empty response!")

#     except Exception as e:
#         print(f"❌ Google TTS Error: {e}")
#         return False

#     return True


# def receive_user_input():
#     """Captures user voice input and converts it to text."""
#     with MicrophoneStream(RATE, CHUNK) as stream:
#         with audio_queue.mutex:
#             audio_queue.queue.clear()

#         audio_generator = stream.generator()
#         requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)

#         responses = stt_client.streaming_recognize(streaming_config, requests)

#         for response in responses:
#             if not response.results:
#                 continue
#             result = response.results[0]
#             if result.is_final:
#                 return result.alternatives[0].transcript.strip()
#     return ""


# def extract_field_value(field, user_input):
#     """Uses Anthropic's Claude via Vertex AI to intelligently extract field values."""
#     prompt = f"""
#     You are an AI assistant helping extract structured information from a user's spoken response.
#     The field you need to extract is: {field['field']}.

#     User's Response: "{user_input}"
    
#     Extract the most relevant value and return it in a structured JSON format:
#     ```json
#         {{
#             "value": "Extracted Value"
#         }}
#     ```
#     """

#     response = client.messages.create(
#         model="claude-3-5-sonnet@20240620",
#         max_tokens=5000,
#         messages=[{"role": "user", "content": prompt}]
#     )
#     res=response.model_dump_json(indent=2)
#     response_dictionary = json.loads(res)

#     print(response)
#     try:
#         import re
#         match = re.search(r'```json\s*\{\s*"value"\s*:\s*"([^"]+)"\s*\}\s*```', response_dictionary["content"][0]['text'])

#         if match:
#             extracted_value = match.group(1)
#             return extracted_value
#         else:
#             print("No match found")
#     except json.JSONDecodeError:
#         return user_input.strip() 


# @app.route('/')
# def index():
#     """Renders the registration form."""
#     return render_template('index.html', form_fields=form_fields, form_data=form_data)


# @app.route('/start', methods=['POST'])
# def start_form_filling():
#     """Begins voice-based form filling."""
#     global current_field_index, form_data
#     form_data = {}
#     current_field_index = 0

#     def fill_form():
#         global current_field_index
#         for field in form_fields:
#             synthesize_speech(field["prompt"])

#             while True:
#                 user_text = receive_user_input()
#                 extracted_value = extract_field_value(field, user_text)
#                 print("extracted_value",extracted_value)

#                 if extracted_value:
#                     form_data[field["field"]] = extracted_value
#                     break  # Proceed to next field
#                 else:
#                     synthesize_speech(f"I didn't catch that correctly. Could you please repeat?")

#         synthesize_speech("Great! Your form is completed. Please review the details.")

#     thread = threading.Thread(target=fill_form)
#     thread.start()

#     return jsonify({"message": "Voice-based form filling started!"})


# if __name__ == '__main__':
#     app.run(debug=True,port=5003)
import os
import queue
import threading
import json
import random
from flask import Flask, render_template, request, jsonify
from google.cloud import speech, texttospeech
import pyaudio
from anthropic import AnthropicVertex

# Flask app setup
app = Flask(__name__)

# Google API Credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "creds.json"

# Audio Configurations
RATE = 16000
CHUNK = int(RATE / 10)
audio_queue = queue.Queue()

# Initialize Google Clients
stt_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

streaming_config = speech.StreamingRecognitionConfig(
    config=speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
    ),
    interim_results=False
)

# Initialize Anthropic's Claude via Vertex AI
LOCATION = "us-east5"
client = AnthropicVertex(region=LOCATION, project_id="alan-suite")
conversation_history = []

# Registration Form Fields
form_fields = [
    {"field": "full_name"},
    {"field": "email"},
    {"field": "phone_number"},
    {"field": "address"},
    {"field": "dob"}
]
form_data = {}
current_field_index = 0


class MicrophoneStream:
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1, rate=self.rate, input=True, frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        self._closed = False

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        if in_data:
            audio_queue.put(in_data)
        return None, pyaudio.paContinue

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self._audio_interface.terminate()
        self._closed = True

    def generator(self):
        while not self._closed:
            chunk = audio_queue.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = audio_queue.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


def synthesize_speech(text):
    """Convert text to speech using Google TTS."""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    try:
        response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        filename = "response.wav"

        if response.audio_content:
            with open(filename, "wb") as out:
                out.write(response.audio_content)

            os.system(f"ffplay -nodisp -autoexit {filename} > /dev/null 2>&1")

            if os.path.exists(filename):
                os.remove(filename)
        else:
            print("❌ Google TTS returned empty response!")

    except Exception as e:
        print(f"❌ Google TTS Error: {e}")
        return False

    return True


def receive_user_input():
    """Captures user voice input and converts it to text."""
    with MicrophoneStream(RATE, CHUNK) as stream:
        with audio_queue.mutex:
            audio_queue.queue.clear()

        audio_generator = stream.generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)

        responses = stt_client.streaming_recognize(streaming_config, requests)

        for response in responses:
            if not response.results:
                continue
            result = response.results[0]
            if result.is_final:
                return result.alternatives[0].transcript.strip()
    return ""


def generate_conversational_question(field_name):
    """Uses Claude AI to generate friendly, natural questions for each field."""
    prompt = f"""
    You are an AI assistant helping fill out a registration form.
    Generate a friendly, conversational question to ask the user about their {field_name}.
    Keep it engaging and natural, avoiding robotic phrasing.Strictly make it in half line only
    strictly give response in below format.Extract the most relevant value and return it in a structured JSON format:
    ```json
        {{
            "value": "Generated Question"
        }}
    ```
    """

    response = client.messages.create(
        model="claude-3-5-sonnet@20240620",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}]
    )
    res=response.model_dump_json(indent=2)
    response_dictionary = json.loads(res)
    import re
    match = re.search(r'```json\s*\{\s*"value"\s*:\s*"([^"]+)"\s*\}\s*```', response_dictionary["content"][0]['text'])

    if match:
        extracted_value = match.group(1)
        return extracted_value
    else:
        print("No match found")

    return response.content[0].text.strip()


def generate_friendly_response(user_input):
    """Uses Claude AI to generate a friendly response based on user input."""
    prompt = f"""
    Respond warmly and conversationally to the following user input:
    "{user_input}"

    Keep it short, positive, and engaging.Strictly make it in half line only and upto 3-4 words
    strictly give response in below format.Extract the most relevant value and return it in a structured JSON format:
    ```json
        {{
            "value": "output"
        }}
    ```
    """

    response = client.messages.create(
        model="claude-3-5-sonnet@20240620",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}]
    )
    res=response.model_dump_json(indent=2)
    response_dictionary = json.loads(res)
    import re
    match = re.search(r'```json\s*\{\s*"value"\s*:\s*"([^"]+)"\s*\}\s*```', response_dictionary["content"][0]['text'])

    if match:
        extracted_value = match.group(1)
        return extracted_value
    else:
        print("No match found")

    return response.content[0].text.strip()

def extract_field_value(field, user_input):
    """Uses Anthropic's Claude via Vertex AI to intelligently extract field values."""
    prompt = f"""
    You are an AI assistant helping extract structured information from a user's spoken response.
    The field you need to extract is: {field['field']}.

    User's Response: "{user_input}"
    
    Extract the most relevant value and return it in a structured JSON format:
    ```json
        {{
            "value": "Extracted Value"
        }}
    ```
    """

    response = client.messages.create(
        model="claude-3-5-sonnet@20240620",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}]
    )
    res = response.model_dump_json(indent=2)
    response_dictionary = json.loads(res)

    try:
        import re
        match = re.search(r'```json\s*\{\s*"value"\s*:\s*"([^"]+)"\s*\}\s*```', response_dictionary["content"][0]['text'])
        if match:
            extracted_value = match.group(1)
            return extracted_value.strip()
        else:
            print("❌ No match found. Returning raw user input.")
            return user_input.strip()
    except json.JSONDecodeError:
        return user_input.strip()


@app.route('/')
def index():
    """Renders the registration form."""
    return render_template('index.html', form_fields=form_fields, form_data=form_data)


@app.route('/start', methods=['POST'])
def start_form_filling():
    """Begins conversational, voice-based form filling."""
    global current_field_index, form_data
    form_data = {}
    current_field_index = 0

    def fill_form():
        global current_field_index, form_data, conversation_history

        conversation_history.append({"role": "assistant", "content": "Let's begin the form-filling process. I'll ask you some questions in a friendly way."})

        for field in form_fields:
            # AI generates a natural, conversational question for the field
            prompt = f"""
            You are a friendly AI assisting with form-filling. Ask the user a conversational and engaging question to get their {field['field'].replace('_', ' ')}.
            Make sure the question sounds natural, warm, and inviting.striclty have it in half line only and upto 3-4 words and be very clear in asking question professionally.Don't repeat his name everytime as it might sound robotic
            """

            # Get AI-generated question
            response = client.messages.create(
                model="claude-3-5-sonnet@20240620",
                max_tokens=5000,
                messages=conversation_history + [{"role": "user", "content": prompt}]
            )

            question = response.content[0].text.strip()
            conversation_history.append({"role": "assistant", "content": question})

            # Speak the AI-generated question
            synthesize_speech(question)

            # Capture user response
            user_text = receive_user_input()
            conversation_history.append({"role": "user", "content": user_text})

            # Single LLM call for extracting value + friendly response
            extract_prompt = f"""
            You are an AI extracting structured data from a user's response.
            Extract only the necessary value for {field['field']} from the user's statement.
            Format your response strictly in JSON:

            ```json
            {{
                "value": "Extracted Value"
            }}
            ```
            """

            response = client.messages.create(
                model="claude-3-5-sonnet@20240620",
                max_tokens=5000,
                messages=conversation_history + [{"role": "user", "content": extract_prompt}]
            )

            res = response.model_dump_json(indent=2)
            response_dictionary = json.loads(res)

            try:
                import re
                match = re.search(r'```json\s*\{\s*"value"\s*:\s*"([^"]+)"\s*\}\s*```', response_dictionary["content"][0]['text'])
                if match:
                    extracted_value = match.group(1).strip()
                    form_data[field["field"]] = extracted_value
                else:
                    form_data[field["field"]] = user_text.strip()  # Fallback to raw input if extraction fails
            except json.JSONDecodeError:
                form_data[field["field"]] = user_text.strip()

            # AI generates a friendly confirmation response
            friendly_response_prompt = f"""
            The user provided their {field['field']} as "{form_data[field['field']]}". 
            Generate a short, warm response acknowledging the input.striclty have it in half line only and upto 3-4 words
            """

            response = client.messages.create(
                model="claude-3-5-sonnet@20240620",
                max_tokens=50,
                messages=conversation_history + [{"role": "user", "content": friendly_response_prompt}]
            )

            friendly_response = response.content[0].text.strip()
            conversation_history.append({"role": "assistant", "content": friendly_response})

            # Speak the AI confirmation response
            synthesize_speech(friendly_response)

        # AI gives a final summary
        summary_text = "Awesome! Here's what I have recorded:\n" + "\n".join(
            [f"{f['field'].replace('_', ' ').title()}: {form_data.get(f['field'], 'Not provided')}" for f in form_fields]
        )

        conversation_history.append({"role": "assistant", "content": summary_text})
        synthesize_speech(summary_text)
        synthesize_speech("If everything looks good, you're all set!")



    thread = threading.Thread(target=fill_form)
    thread.start()

    return jsonify({"message": "Conversational AI form filling started!"})


if __name__ == '__main__':
    app.run(debug=True,port=5003)


