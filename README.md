# chatbot-using-aws
This is a conversational chatbot using AWS

Services Used for END to END conversational Engine

1. Speech to Text: Amazon Transcribe (Hindi)
2. LLM Model: Amazon Nova Lite using Amazon Bedrock Agent
3. Text to Speech: Amazon Polly

Python Libraries to Download
```commandline
pip install awscli // To configure AWS credentials
brew install portaudio
pip install pyaudio // To configure audio inputs and outputs
pip install asyncio // To run the code asynchronously
python -m pip install boto3 // To run AWS client in local
pip install -U thread // To configure multi threading
pip intall uuid //To generate uuid as session id
python -m pip install amazon-transcribe // To install Amazon Transcribe Agent
```
To configure AWS credentials using AWS CLI
```commandline
aws configure
aws_access_key_id= //Enter AWS Access Key Id
aws_secret_access_key= //Enter AWS Access Key
region = us-east-1
output = json
```
# Bedrock Agent already configured in AWS Console.
https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/agents/R5UEJWGSP2.

Note: Run the python file from Command Line since IDEA does not support input from microphone.
