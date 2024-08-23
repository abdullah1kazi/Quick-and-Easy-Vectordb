import streamlit as st
import pandas as pd
import numpy as np
from transformers import DistilBertTokenizer, DistilBertModel
import torch
from sklearn.metrics.pairwise import cosine_similarity
import os
from io import BytesIO
import PyPDF2

# Initialize DistilBERT model and tokenizer
@st.cache_resource
def load_model():
    tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
    model = DistilBertModel.from_pretrained('distilbert-base-uncased')
    return tokenizer, model

tokenizer, model = load_model()

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

def chunk_text(text, chunk_size=1000, overlap=200):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def read_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def main():
    st.title("Vector DB Search App")

    # File upload
    uploaded_file = st.file_uploader("Choose a file", type=['txt', 'pdf'])
    if uploaded_file is not None:
        # Read file content
        if uploaded_file.type == "text/plain":
            text = uploaded_file.read().decode()
        elif uploaded_file.type == "application/pdf":
            text = read_pdf(uploaded_file)
        else:
            st.error("Unsupported file type")
            return

        # Chunk the text
        chunks = chunk_text(text)

        # Create DataFrame
        df = pd.DataFrame({
            'chunk_id': range(len(chunks)),
            'chunk_text': chunks,
            'document_id': [uploaded_file.name] * len(chunks),
            'document_download_link': [''] * len(chunks),  # You'll need to implement file storage and link generation
        })

        # Generate embeddings with progress bar
        embeddings = []
        with st.status("Processing document...", expanded=True) as status:
            st.write("Generating embeddings...")
            progress_bar = st.progress(0)
            for i, chunk in enumerate(df['chunk_text']):
                embeddings.append(get_embedding(chunk))
                progress = (i + 1) / len(df)
                progress_bar.progress(progress)
                status.update(label=f"Processing document... ({i+1}/{len(df)} chunks)")
            
            df['vector_embedding'] = embeddings
            status.update(label="Document processing complete!", state="complete")

        # Save to CSV
        csv = df.to_csv(index=False).encode()
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="vector_db.csv",
            mime="text/csv",
        )

        # Search functionality
        search_query = st.text_input("Enter your search query")
        if search_query:
            query_embedding = get_embedding(search_query)
            df['similarity'] = df['vector_embedding'].apply(lambda x: cosine_similarity([x], [query_embedding])[0][0])
            results = df.sort_values('similarity', ascending=False).head(5)
            st.write(results[['chunk_text', 'similarity']])

if __name__ == "__main__":
    main()
