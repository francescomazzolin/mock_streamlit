#%%

# Import Libraries
import streamlit as st
import os
from dotenv import load_dotenv
from docx import Document
import openai
import pandas as pd
import re
import time
import pickle
import importlib
import configparser
import tiktoken

# PDF Chatbot Libraries
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI

# Custom Functions Module
import to_pager_functions_2 as fc
importlib.reload(fc)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OpenAI_key")

# Check API key
if openai.api_key is None:
    st.error("Error: OpenAI API key not found. Make sure it is set in environment variables or Streamlit secrets.")
    st.stop()

# Set Page Configuration
st.set_page_config(page_title='AI Assistant', page_icon=':robot:')

# Main Title
st.title("AI Assistant Application")

# Drop-Down Menu for Functionality Selection
option = st.selectbox(
    'Select a functionality:',
    ('Chatbot with PDFs', 'Document Generator')
)

# Supporting Functions for Chatbot
def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        try:
            pdf_reader = PdfReader(pdf)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        except Exception as e:
            st.error(f"Error processing {pdf.name}: {e}")
    return text

def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings(openai_api_key=openai.api_key)
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore

def get_conversation_chain(vectorstore):
    llm = ChatOpenAI(
        model_name="gpt-4", 
        temperature=0.1,
        openai_api_key=openai.api_key
    )
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain

def handle_userinput(user_question):
    if st.session_state.conversation is None:
        st.warning("Please upload and process the documents first!")
        return

    # Get the response from the conversation chain
    response = st.session_state.conversation({'question': user_question})
    answer = response['answer']  # Assuming response contains an 'answer' key

    # Display the response in Streamlit
    st.write(answer)

# Chatbot Functionality
def chatbot_with_pdfs():

    st.header('Chat with multiple PDFs :books:')

    # Initialize Session State
    if 'conversation' not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None  

    # Sidebar for uploading PDFs
    with st.sidebar:
        st.subheader('Your documents')
        pdf_docs = st.file_uploader('Upload your PDFs here and click on Process', 
                                    accept_multiple_files=True)
        if st.button('Process'):
            if pdf_docs:
                with st.spinner('Processing'):
                    # Get PDF text
                    raw_text = get_pdf_text(pdf_docs)
                    
                    # Get the text chunks
                    text_chunks = get_text_chunks(raw_text)
                    # st.write(text_chunks)  # Optionally display chunks

                    # Create our vector store with embeddings
                    vectorstore = get_vectorstore(text_chunks)

                    # Create conversation chain
                    st.session_state.conversation = get_conversation_chain(vectorstore)
                    st.success('Processing complete! You can now ask questions.')
            else:
                st.warning('Please upload at least one PDF file before processing.')

    # Input for questions
    user_question = st.text_input('Ask a question about your documents:')
    if user_question:
        handle_userinput(user_question)

# Document Generator Functionality
def document_generator():

    # Preloaded Files
    xlsx_file = "prompt_db.xlsx"
    docx_file = "to_pager_template.docx"

    doc_copy = Document(docx_file)
    
    # Initialize the OpenAI client
    client = openai.OpenAI()

    
    # Create a ConfigParser instance
    config = configparser.ConfigParser()
    
    # Read the .cfg file
    config.read('assistant_config.cfg')  # Replace with your file path


    
    st.header('Document Generator :page_facing_up:')
    
    # Inputs or configurations for the document generator
    st.subheader('Configuration')

    # Template Path Input
    pdf_docs = st.file_uploader('Upload your PDFs here and click on Process', 
                                    accept_multiple_files=True)
    st.write(f'{type(pdf_docs)}')
    

    # Start the generation process
    if st.button('Generate Document'):
        with st.spinner('Generating document...'):

            if pdf_docs:
                st.write(f'{type(pdf_docs)}')
                st.write(f'the first entry is: {pdf_docs[0]}')
                
                for uploaded_file in pdf_docs:
                    st.write(f"File Name: {uploaded_file.name}")
                    st.write("Attributes and methods of the UploadedFile object:")
                    st.write(dir(uploaded_file))  # List all attributes and methods
            else:
                st.write("No files uploaded.")
                    
            # Initialize variables
            temp_responses = []
            answers_dict = {}
    
            configuration = fc.assistant_config(config, 'BO')
    
            assistant_identifier = fc.create_assistant(client, 'final_test', configuration)
    
    
            """
            Adding files to the assistant
            """
            file_streams = pdf_docs
            
            fc.load_file_to_assistant(client, assistant_identifier, file_streams)
    
            
            # Retrieve prompts and formatting requirements
            try:
                prompt_list, additional_formatting_requirements, prompt_df = fc.prompts_retriever(
                    'prompt_db.xlsx', ['BO_Prompts', 'BO_Format_add'])
            except Exception as e:
                st.error(f"Error retrieving prompts: {e}")
                return
            
            for prompt_name, prompt_message in prompt_list:
                prompt_message = fc.prompt_creator(prompt_df, prompt_name, 
                                                   prompt_message, additional_formatting_requirements,
                                                   answers_dict)
                
                assistant_response = fc.separate_thread_answers(openai, prompt_message, 
                                                                assistant_identifier)
                
                if assistant_response:
                    temp_responses.append(assistant_response)
                    assistant_response = fc.remove_source_patterns(assistant_response)
                    answers_dict[prompt_name] = assistant_response
                    fc.document_filler(doc_copy, prompt_name, assistant_response)
                else:
                    st.warning(f"No response for prompt '{prompt_name}'.")
    
    
            assistant_identifier = 'asst_vy2MqKVgrmjCecSTRgg0y6oO'
    
    
            prompt_list, additional_formatting_requirements, prompt_df = fc.prompts_retriever('prompt_db.xlsx', 
                                                                                            ['RM_Prompts', 'RM_Format_add'])
            for prompt_name, prompt_message in prompt_list:
    
                prompt_message = fc.prompt_creator(prompt_df, prompt_name, 
                                                prompt_message, additional_formatting_requirements,
                                                answers_dict)
    
                assistant_response = fc.separate_thread_answers(client, prompt_message, 
                                                                assistant_identifier)
                
    
                if assistant_response:
                    print(f"Assistant response for prompt '{prompt_name}': {assistant_response}")

                temp_responses.append(assistant_response)

                assistant_response = fc.remove_source_patterns(assistant_response)

                answers_dict[prompt_name] = assistant_response

                fc.document_filler(doc_copy, prompt_name, assistant_response)

        # Save the modified document
        output_path = 'generated_document.docx'
        doc_copy.save(output_path)
        st.success(f'Document generated and saved as {output_path}')
        # Provide a download link
        with open(output_path, "rb") as doc_file:
            btn = st.download_button(
                label="Download Document",
                data=doc_file,
                file_name=output_path,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

# Main Function
def main():
    if option == 'Chatbot with PDFs':
        chatbot_with_pdfs()
    elif option == 'Document Generator':
        document_generator()
    else:
        st.error("Invalid selection. Please choose a valid functionality.")

if __name__ == '__main__':
    main()
