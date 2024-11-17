import streamlit as st
import requests
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, request, jsonify, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson import ObjectId

from app import jwt


# Define the main function to create the navigational layout
def main():
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None

    if st.session_state.access_token is None:
        st.sidebar.title("Authentication")
        auth_option = st.sidebar.radio("Choose an option", ["Login", "Sign Up"])
        if auth_option == "Login":
            login_page()
        else:
            signup_page()
    else:
        st.sidebar.title("Navigation")
        selection = st.sidebar.radio("Go to", ["Home", "Chat", "Analytics"])

        if selection == "Home":
            home_page()
        elif selection == "Chat":
            chat_page()
        elif selection == "Analytics":
            analytics_page()

def get_username_from_token(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        print(decoded)
        return decoded.get('sub')  # 'sub' is typically where the identity (username) is stored in a JWT
    except:
        return None
# Define the Home page
def home_page():
    username = get_username_from_token(st.session_state.access_token)
    st.title(f"Welcome!")
    st.write("This is your Stock Chatbot and Analytics App")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Go to Chat Page"):
            st.session_state.page = "Chat"
            st.rerun()
    with col2:
        if st.button("Go to Analytics Page"):
            st.session_state.page = "Analytics"
            st.rerun()


# Define the Chat page
def chat_page():
    st.title("Stock Chatbot")
    st.write("Ask me anything about stocks!")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("What would you like to know about stocks?"):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Call the chatbot backend API
        headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
        response = requests.post('http://0.0.0.0:8080/api/chat', json={"query": prompt},headers=headers)
        if response.ok:
            bot_response = response.json().get('response', 'Sorry, I did not understand that.')
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(bot_response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": bot_response})
        else:
            st.error("Error: Unable to get response from the API.")


# Define the Analytics page
def analytics_page():
    st.title("Stock Analytics")

    # List of companies
    companies = ["Apple", "Google", "Amazon", "Microsoft", "Tesla", "Facebook", "Netflix", "NVIDIA"]
    company_to_symbol = {"Apple":"AAPL", "Microsoft": "MSFT", "Amazon": "AMZN", "Google": "GOOGL", "Facebook": "FB",
        "Tesla":"TSLA", "Netflix": "NFLX","NVIDIA": "NVDA"}

    stock_labels = ["Open", "High", "Low", "Close", "Volume"]

    # Dropdown to select a company
    selected_company = st.selectbox("Select a company for analysis:", companies)

    st.write(f"You selected: {selected_company}")

    start_date = st.date_input("Start Date", value=pd.to_datetime("2024-09-07"))
    end_date = st.date_input("End Date", value=pd.to_datetime("2024-11-07"))

    selected_label = st.selectbox("Select a company for analysis:", stock_labels)


    try:
        data = yf.download(company_to_symbol[selected_company], start=start_date, end=end_date)
        if data.empty:
            st.error("No data found. Please check the ticker symbol or date range.")
        else:
            st.success(f"Data fetched successfully for {selected_company}!")

            # Show the data table
            # st.write("### Stock Data Preview", data.head())

            # Plot the data
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(data.index, data[selected_label], label=selected_label, color="blue")
            ax.set_title(f"{selected_company} Stock Prices ({start_date} to {end_date})")
            ax.set_xlabel("Date")
            ax.set_ylabel("Close Price (USD)")
            ax.grid()
            ax.legend()

            # Display the plot in Streamlit
            st.pyplot(fig)
    except Exception as e:
        st.error(f"An error occurred: {e}")

    # Placeholder for future analytics features
    # st.write("Analytics features coming soon!")

    # You can add more analytics features here, such as:
    # - Historical stock price charts
    # - Financial metrics
    # - News sentiment analysis
    # - Predictive models

def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = requests.post('http://0.0.0.0:8080/api/login', json={"username": username, "password": password})
        if response.ok:
            st.session_state.access_token = response.json().get('access_token')
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")
def signup_page():
    st.title("Sign Up")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    if st.button("Sign Up"):
        if password != confirm_password:
            st.error("Passwords do not match")
        else:
            response = requests.post('http://0.0.0.0:8080/api/signup', json={"username": username, "password": password})
            if response.ok:
                st.success("Account created successfully! Please log in.")
                st.session_state.page = "Login"
                st.rerun()
            else:
                st.error("Username already exists or other error occurred")

# Run the main function
if __name__ == "__main__":
    main()
