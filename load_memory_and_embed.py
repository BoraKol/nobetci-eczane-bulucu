from langchain.embeddings import OpenAIEmbeddings 
from langchain.vectorstores import FAISS # vector db 
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not found")

os.environ["OPENAI_API_KEY"] = api_key

loader = PyPDFLoader("Ilac_ve_Semptom_Danismani/recetesiz_ilac_listesi.pdf")

documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 500 , 
    chunk_overlap = 50
)

docs = text_splitter.split_documents(documents)

embedding = OpenAIEmbeddings(model = "text-embedding-3-large")

vector_db = FAISS.from_documents(docs,embedding)

vector_db.save_local("Ilac_ve_Semptom_Danismani/ilac_listesi_vectorstore")
print("Embedding ve vektor veritabani basarili bir sekilde olusturuldu.")
