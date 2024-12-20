from PyPDF2 import PdfReader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import Chroma
import joblib
import os
import requests
import time
from dotenv import load_dotenv
import warnings

# Load the .env file
load_dotenv()  # This will load the variables from the .env file

# Access the token
API_TOKEN = os.getenv("HF_API_TOKEN")

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
warnings.filterwarnings('ignore')

def query_huggingface(payload):
    """Send a query to Hugging Face Inference API and return the response."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

template = """
<s>[INST] <<SYS>>
You are a helpful AI assistant who has to act as an advocate in the case of country Nepal, not others.
Answer based on the context provided. Don't answer unnecessarily if you don't find the context.
<</SYS>>
{context}
Question: {question}
Helpful Answer: [/INST]
"""

prompt = PromptTemplate.from_template(template)


# Load the PDF and process it
reader = PdfReader('data/fine_tune_data.pdf')
raw_text = ''
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    if text:
        raw_text += text


# Split text into manageable chunks
text_splitter = CharacterTextSplitter(
    separator="\n",
    chunk_size=350,
    chunk_overlap=20,
    length_function=len,
)
texts = text_splitter.split_text(raw_text)

# Load or create embeddings
embeddings_file = "./data/genderviolence.joblib"
if os.path.exists(embeddings_file):
    embeddings = joblib.load(embeddings_file)
else:
    # Use HuggingFace sentence transformer embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    joblib.dump(embeddings, embeddings_file)

vectorstore = Chroma.from_texts(texts, embeddings, persist_directory=None)
retriever = vectorstore.as_retriever()

query = "My husband usually gets drunk and misbehaves with me"

config = {
    'max_new_tokens': 500,  # Adjusted to potentially reduce response time
    'temperature': 0.7,     # Adjusted for more coherent responses
    'context_length' : 2048
}

if query:
    # Start timing the response
    start_time = time.time()

    # Retrieve relevant documents
    documents = retriever.get_relevant_documents(query)
    context = "\n".join([doc.page_content for doc in documents])

    # Format the prompt
    full_prompt = template.format(context=context, question=query)

    # Create the payload with the configuration parameters
    payload = {
        "inputs": full_prompt,
        "parameters": config
    }

    # Send the prompt to Hugging Face Inference API
    api_response = query_huggingface(payload)

    # The response from Hugging Face API is a list of dictionaries
    response_text = api_response[0].get("generated_text", "Sorry, no response generated.")
    
    # Extract the response after the [/INST] marker
    response_start = response_text.find('[/INST]')  # Find the index of the marker
    if response_start != -1:
        # Extract the portion after [/INST]
        response_after_inst = response_text[response_start + len('[/INST]'):].strip()
    else:
        response_after_inst = "Sorry, no valid answer generated."

    # End timing the response
    end_time = time.time()

    # Display the response
    print("\nHelpful Answer:")
    print(response_after_inst)
    print(f"\nResponse time: {end_time - start_time:.2f} seconds")
else:
    print("Please enter a question.")
