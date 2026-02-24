import streamlit as st
from modelling.function_gemini import PropertyMatchmaker
from dotenv import load_dotenv

load_dotenv()

def run_streamlit_app():
    st.set_page_config(page_title="PropMatch AI", page_icon="🏠")
    st.title("🏠 Real Estate Matchmaker")
    st.caption("Powered by Llama-3.3 & Groq")

    # Initialize the Matchmaker in Session State so it doesn't reload every click
    if "matcher" not in st.session_state:
        st.session_state.matcher = PropertyMatchmaker()
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("E.g., Find me a 3-bed villa in Central with a pool"):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate Assistant Response
        with st.chat_message("assistant"):
            with st.spinner("Searching database..."):
                # Combine history for context if needed, or just send the prompt
                response = st.session_state.matcher.search_properties(prompt)
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    run_streamlit_app()