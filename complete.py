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

# Custom Functions Module
import to_pager_functions_2 as fc
importlib.reload(fc)

import pdf_chat_functions as pc
importlib.reload(pc)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OpenAI_key")

# Check API key
if openai.api_key is None:
    st.error("Error: OpenAI API key not found. Make sure it is set in environment variables or Streamlit secrets.")
    st.stop()

# Set Page Configuration
st.set_page_config(page_title='AI Gradiente', page_icon=':robot:')

# Add custom font and styles
st.markdown("""
    <style>

    /* Apply a generic font globally */
    html, body, [class*="css"] {
        font-family: Arial, sans-serif;
    }   
    
    /* Optional: Customize specific elements */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 500;
        color: #333333;  /* Adjust header color if needed */
    }
    .stButton>button {
        font-family: Arial, sans-serif;
        font-weight: 700;
        color: white;
        background-color: #D32F2F;  /* Button background color */
        border-radius: 5px;
        border: none;
    }
    .stMarkdown {
        color: #424242;  /* Paragraph text color */
    }
    </style>
""", unsafe_allow_html=True)

# Display Banner Image
banner_path = "AI GRADIENTE VETTORIALE_page-0001.jpg"  # Update with the correct path
st.image(banner_path, use_container_width=True)

# Main Title
#st.title("AI Assistant Application")

st.markdown("<h3 style='font-size:25px;'>Select your application:</h3>", unsafe_allow_html=True)

# Inject custom CSS to reduce the margin above the select box
st.markdown(
    """
    <style>
    div[data-testid="stSelectbox"] {
        margin-top: -50px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

option = st.selectbox(
    '',  # Leave label empty because it's already displayed above
    ('Select an application', 'Chatbot with PDFs', 'Document Generator')
)

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
                    raw_text = pc.get_pdf_text(pdf_docs)
                    
                    # Get the text chunks
                    text_chunks = pc.get_text_chunks(raw_text)
                    # st.write(text_chunks)  # Optionally display chunks

                    # Create our vector store with embeddings
                    vectorstore = pc.get_vectorstore(text_chunks)

                    # Create conversation chain
                    st.session_state.conversation = pc.get_conversation_chain(vectorstore)
                    st.success('Processing complete! You can now ask questions.')
            else:
                st.warning('Please upload at least one PDF file before processing.')

    # Input for questions
    user_question = st.text_input('Ask a question about your documents:')
    if user_question:
        st.handle_userinput(user_question)

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
    st.subheader('Upload your files here:')

    st.markdown(
    """
    <style>
    div[data-testid="stFileUploader"] {
        margin-top: -50px;
    }
    </style>
    """,
    unsafe_allow_html=True
    )


    # Template Path Input
    pdf_docs = st.file_uploader('',accept_multiple_files=True)
    #st.write(f'{type(pdf_docs)}')
    

    # Start the generation process
    if st.button('Generate Document'):
        with st.spinner('Generating document...'):

            if pdf_docs:
                st.write('Files correctly uploaded')
                
            else:
                st.write("No files uploaded.")
                    
            # Initialize variables
            temp_responses = []
            answers_dict = {}
    
            configuration = fc.assistant_config(config, 'BO')
    
            assistant_identifier = fc.create_assistant(client, 'final_test', configuration)

            file_streams = pdf_docs

            vector_store = client.beta.vector_stores.create(name="Business Overview")
            vector_store_id = vector_store.id
            
            fc.load_file_to_assistant(client, vector_store_id,
                                      assistant_identifier, file_streams)
    
            
            # Retrieve prompts and formatting requirements
            try:
                prompt_list, additional_formatting_requirements, prompt_df = fc.prompts_retriever(
                    'prompt_db.xlsx', ['BO_Prompts', 'BO_Format_add'])
            except Exception as e:
                st.error(f"Error retrieving prompts: {e}")
                return
            
            #print(f'{prompt_list}')
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
            
            """
            REFERENCE MARKET CREATION
            """
            
            #assistant_identifier = 'asst_vy2MqKVgrmjCecSTRgg0y6oO'
            configuration = fc.assistant_config(config, 'RM')
            assistant_identifier = fc.create_assistant(client, 'final_test', configuration)

            vector_store = client.beta.vector_stores.create(name="Reference Market")
            vector_store_id = vector_store.id
            
            fc.load_file_to_assistant(client, vector_store_id,
                                      assistant_identifier, file_streams)
            
            st.write("Original file streams")
            st.write(f"{file_streams}")
            st.write(f"{type(file_streams)}")
    
            retrieved_files = fc.html_retriever(file_streams)

            st.write("Retrieved files")
            st.write(f"{retrieved_files}")
            #st.write(f"{type(retrieved_files)}")

            
            fc.load_file_to_assistant(client, vector_store_id,
                                      assistant_identifier, retrieved_files,
                                      uploaded = False)


    
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
        pass

if __name__ == '__main__':
    main()
