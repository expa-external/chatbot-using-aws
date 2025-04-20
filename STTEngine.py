import asyncio
import pyaudio
import boto3
import threading
import uuid
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

chunkValue = 1024  # Record in chunk of 1024 samples
sample_format = pyaudio.paInt16  # 16bits per sample
channels = 1
fs = 16000  # Record at 44100 samples per second

# bedrock_client = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
bedrock_agent_runtime = boto3.client(service_name='bedrock-agent-runtime', region_name='us-east-1')
polly_client = boto3.client(service_name='polly', region_name='us-east-1')

system_prompt = ("You are a supportive and motivational conversational AI designed to enhance the user's English "
                 "speaking and communication skills. You are a personal mentor. You are not a virtual girlfriend, "
                 "boyfriend, clinical therapist, or coach. Your primary focus is to foster conversations around the "
                 "themes of Communication, Ethics, Gender Sensitivity, Critical Thinking, and Entrepreneurship. You "
                 "will maintain an encouraging tone and avoid personal remarks or comments on the user's responses. "
                 "Your responses should be concise and directly related to the user's last question (starting with "
                 "'User:'). Refrain from using special characters or symbols in your replies, and stick to plain text "
                 "in all interactions. Always provide a direct and concise answer to the user's input. Do not include "
                 "any internal reasoning or '<think>' sections in your replies. Focus solely on responding to the "
                 "user's question or prompt.")
messages = []
inference_config = {
    "maxTokens": 150,
    "temperature": 0.7
}
additional_model_fields = {}
audio = pyaudio.PyAudio()
stream = audio.open(
    format=sample_format,
    channels=channels,
    rate=fs,
    input=True,
    frames_per_buffer=chunkValue
)
sessionId = str(uuid.uuid4())


# Play audio received from Polly
def play_audio(audio_stream):
    player = audio.open(format=audio.get_format_from_width(2),
                        channels=1,
                        rate=fs,
                        output=True)
    for chunk in audio_stream.iter_chunks(chunkValue):
        if chunk:
            player.write(chunk)
    player.stop_stream()
    player.close()


# Synthesize speech using polly
def synthesize_and_play(text):
    def _play():
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat="pcm",
            VoiceId="Aditi",
            SampleRate=str(fs)
        )
        if "AudioStream" in response:
            play_audio(response["AudioStream"])

    threading.Thread(target=_play()).start()


# Custom Handler to handle the result from output stream
class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        for result in transcript_event.transcript.results:
            if result.is_partial:
                print("Partial output: ", result.alternatives[0].transcript)
            else:
                print("Final output: ", result.alternatives[0].transcript)
                await send_to_nova_streaming(result.alternatives[0].transcript)


async def send_to_nova_streaming(transcribed_text):
    # if len(messages) == 0:
    #     system_prompts = [{"text": system_prompt}]
    # else:
    #     system_prompts = []
    message = [{"role": "user", "content": [{"text": transcribed_text}]}]
    messages.append(message)
    # response = bedrock_client.converse_stream(
    #     modelId="amazon.nova-lite-v1:0",
    #     messages=message,
    #     system=system_prompts,
    #     inferenceConfig=inference_config,
    #     additionalModelRequestFields=additional_model_fields
    # )

    response = bedrock_agent_runtime.invoke_agent(
        agentId="R5UEJWGSP2",
        agentAliasId="S77DLQKDCC",
        sessionId=sessionId,
        input={'text': transcribed_text},
        streamingConfigurations={
            'streamFinalResponse': True
        }
    )
    buffer = ""

    for event in response["completion"]:
        if "chunk" in event:
            text_chunk = event["chunk"]["bytes"].decode("utf-8")
            print(text_chunk, end="", flush=True)
            buffer += text_chunk
            if text_chunk.strip().endswith(('.', '!', '?')):
                synthesize_and_play(buffer.strip())
                buffer = ""
    if buffer.strip():
        synthesize_and_play(buffer.strip())

    # current_response = ""
    #
    # out_stream = response.get('stream')
    # if out_stream:
    #     for event in out_stream:
    #
    #         if 'messageStart' in event:
    #             print(f"\nRole: {event['messageStart']['role']}")
    #
    #         if 'contentBlockDelta' in event:
    #             delta = event['contentBlockDelta']['delta']['text']
    #             print(delta, end="", flush=True)
    #             current_response += delta
    #
    #         if 'messageStop' in event:
    #             print("-----Nova Complete------")
    #             synthesize_and_play(current_response.strip())
    #             current_response = ""
    #             print(f"\nStop reason: {event['messageStop']['stopReason']}")
    #
    #         if 'metadata' in event:
    #             metadata = event['metadata']
    #             if 'usage' in metadata:
    #                 print("\nToken usage")
    #                 print(f"Input tokens: {metadata['usage']['inputTokens']}")
    #                 print(
    #                     f":Output tokens: {metadata['usage']['outputTokens']}")
    #                 print(f":Total tokens: {metadata['usage']['totalTokens']}")
    #             if 'metrics' in event['metadata']:
    #                 print(
    #                     f"Latency: {metadata['metrics']['latencyMs']} milliseconds")


# This is used to asynchronously wraps the input stream from mic and forwarding it to asyncio.Queue()
# Mic audio streamer
async def mic_stream():
    try:
        while True:
            data = stream.read(chunkValue, exception_on_overflow=False)
            yield data, None
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


# This is to use raw data from microphone and pass it to input stream of transcribe
async def write_chunks(out_stream):
    async for chunk, status in mic_stream():
        await out_stream.input_stream.send_audio_event(audio_chunk=chunk)
    await out_stream.input_stream.end_stream()


async def basic_transcribe():
    # Set up AWS client for the region to call transcribe
    client = TranscribeStreamingClient(region="us-east-1")

    # Start transcription to generate input stream
    in_stream = await client.start_stream_transcription(
        language_code="hi-IN",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
        enable_partial_results_stabilization=True,
        partial_results_stability="medium"
    )

    # Instantiate the handler and start processing events
    handler = MyEventHandler(in_stream.output_stream)
    await asyncio.gather(write_chunks(in_stream), handler.handle_events())


try:
    asyncio.run(basic_transcribe())
except KeyboardInterrupt:
    print("Process interrupted by user.")
finally:
    print("Cleaning up...")
    stream.stop_stream()
    stream.close()
    audio.terminate()
