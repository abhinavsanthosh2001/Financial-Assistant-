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
import numpy as np

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
        st.sidebar.markdown("---")

        # Navigation
        st.sidebar.subheader("Navigation")
        selection = st.sidebar.radio("Go to", ["Home", "Chat", "Analytics"])

        st.sidebar.markdown("---")

        # Market Overview
        st.sidebar.subheader("Market Overview")
        # You would typically fetch this data from an API
        st.sidebar.metric("S&P 500", "5,870.62", "-1.32%")
        st.sidebar.metric("NASDAQ", "78.76", "+0.70")
        st.sidebar.metric("DOW", "43,444.99", "+0.70%")

        # User Profile
        if 'user_name' not in st.session_state:
            st.session_state.user_name = ""

        # Main Content
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
    st.title("Welcome to FinChat!")
    st.write("Your AI-powered financial instructor and stock market guide")

    st.markdown("""
    ## Our Main Features:
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Financial Educator Chatbot")
        st.markdown("""
        - 24/7 personalized financial advice
        - Real-time stock market insights
        - Interactive Q&A on financial topics
        - Tailored learning experience
        """)

    with col2:
        st.subheader("2. Stock Analytics")
        st.markdown("""
        - Graphical representation of any stock
        - Compare performance of any 2 stocks
        - Interactive charts and visualizations
        - Historical data analysis
        """)

    st.markdown("---")

    st.markdown("""
    ## Additional Features:
    - Educational resources on investing and finance
    - Real-time market updates
    - Personalized investment recommendations
    """)

    st.markdown("---")

    st.markdown("""
    ## Based on your recent searches...
    ### Top Financial Educational Blogs
    """)

    blogs = [
        ("Online Trading for Beginners", "https://www.google.com/aclk?sa=l&ai=DChcSEwjb1pjf6-OJAxWtLdQBHbR8GR4YABABGgJvYQ&co=1&ase=2&gclid=CjwKCAiAxea5BhBeEiwAh4t5KzWbMyfw0HZR27c7X08wS54Z8L1VDcs-4LFKRR3P5kjKgZNlWV5-LBoCUt8QAvD_BwE&sig=AOD64_1fF7PaVStHRyLWUIVxep4ckf1CKA&q&nis=4&adurl&ved=2ahUKEwjs_5Lf6-OJAxVRLdAFHUimClAQ0Qx6BAgKEAE"),
        ("The Happy Saver", "https://www.thehappysaver.com/"),
        ("Afford Anything", "https://affordanything.com/"),
        ("Schwab Starter Kit", "https://www.google.com/aclk?sa=l&ai=DChcSEwjb1pjf6-OJAxWtLdQBHbR8GR4YABADGgJvYQ&co=1&ase=2&gclid=CjwKCAiAxea5BhBeEiwAh4t5K8--4xngdwsKgFSEYypOu-g2WsZAL3yHXsk683ohUQP6B8F-I-X7_xoCBrEQAvD_BwE&sig=AOD64_37OGFg2yEoqhe5I9Tm7jLiyiP6mw&q&nis=4&adurl&ved=2ahUKEwjs_5Lf6-OJAxVRLdAFHUimClAQ0Qx6BAgLEAE"),
        ("Of Dollars and Data", "https://ofdollarsanddata.com/"),
        ("The Big Picture", "https://ritholtz.com/"),
        ("The Intellectual Investor", "https://www.theintellectualinvestor.com/"),
        ("Crossing Wall St", "https://www.crossingwallstreet.com/"),
    ]

    for blog_name, blog_url in blogs:
        st.markdown(f"- [{blog_name}]({blog_url})")

    st.markdown("---")

    st.info(
        "FinanceBot uses advanced AI to provide up-to-date financial information and personalized advice. However, always consult with a professional financial advisor for important financial decisions.")# Define the Chat page


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
    company_to_symbol = {"Apple":"AAPL", "Microsoft": "MSFT", "Amazon": "AMZN", "Google": "GOOGL", "Facebook": "META",
        "Tesla":"TSLA", "Netflix": "NFLX","NVIDIA": "NVDA"}

    stock_labels = ["Open", "High", "Low", "Close", "Volume"]

    # Dropdown to select a company
    # selected_company = st.selectbox("Select a company for analysis:", companies)

    selected_companies = st.multiselect("Select up to two companies for analysis:", companies, max_selections=2)

    if len(selected_companies) == 1:
        st.write(f"You selected: {selected_companies[0]}")
    elif len(selected_companies) == 2:
        st.write(f"You selected: {selected_companies[0]} and {selected_companies[1]}")
    

    start_date = st.date_input("Start Date", value=pd.to_datetime("2024-09-07"))
    end_date = st.date_input("End Date", value=pd.to_datetime("2024-11-07"))

    selected_label = st.selectbox("Select a stock attribute:", stock_labels)
    color1 = 'yellow'
    color2 = 'cyan'

    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))

        data_dict = {}
        for company in selected_companies:
            data = yf.download(company_to_symbol[company], start=start_date, end=end_date)
            if data.empty:
                st.error(f"No data found for {company}. Please check the ticker symbol or date range.")
            else:
                data_dict[company] = data

        if len(selected_companies) == 2 and all(not data.empty for data in data_dict.values()):
            st.success(f"Data fetched successfully for {' and '.join(selected_companies)}!")

            # if comparison_method == "Dual Y-Axis" and len(selected_companies) == 2:
            ax2 = ax.twinx()
            
            data1 = data_dict[selected_companies[0]][selected_label].values
            data2 = data_dict[selected_companies[1]][selected_label].values
            
            line1, = ax.plot(data_dict[selected_companies[0]].index, data1, 
                            label=f"{selected_companies[0]} - {selected_label}", color=color1)
            line2, = ax2.plot(data_dict[selected_companies[1]].index, data2, 
                            label=f"{selected_companies[1]} - {selected_label}", color=color2)
            
            # Calculate the range for each dataset
            min1, max1 = np.min(data1), np.max(data1)
            min2, max2 = np.min(data2), np.max(data2)
            range1 = max1 - min1
            range2 = max2 - min2
            
            # Calculate the maximum range and adjust limits
            max_range = max(range1, range2)
            buffer = max_range * 0.1
            
            ax.set_ylim(min1 - buffer, min1 + max_range + buffer)
            ax2.set_ylim(min2 - buffer, min2 + max_range + buffer)
            
            ax.set_ylabel(f"{selected_companies[0]} {selected_label} Price (USD)", color=color1)
            ax2.set_ylabel(f"{selected_companies[1]} {selected_label} Price (USD)", color=color2)
            
            ax.tick_params(axis='y', labelcolor=color1)
            ax2.tick_params(axis='y', labelcolor=color2)
            
            # Combine legends
            lines = [line1, line2]
            ax.legend(lines, [l.get_label() for l in lines], loc='upper left')

            ax.set_title(f"Stock {selected_label} Comparison ({start_date} to {end_date})")
            ax.set_xlabel("Date")
            ax.grid(True, alpha=0.3)

            st.pyplot(fig)

        elif len(selected_companies) == 1:
            company = selected_companies[0]

            if data.empty:
                st.error(f"No data found for {company}. Please check the ticker symbol or date range.")
            else:
                ax.plot(data.index, data[selected_label], label=f"{company} - {selected_label}", color=color1)

            if all(not data.empty for data in [yf.download(company_to_symbol[company], start=start_date, end=end_date) for company in selected_companies]):
                st.success(f"Data fetched successfully for {' and '.join(selected_companies)}!")

                ax.set_title(f"Stock Prices Comparison ({start_date} to {end_date})")
                ax.set_xlabel("Date")
                ax.set_ylabel(f"{selected_label} Price (USD)", color=color1)
                ax.grid()
                ax.legend()

                # Display the plot in Streamlit
                st.pyplot(fig)


    except Exception as e:
        st.error(f"An error occurred: {e}")



    if len(selected_companies) == 2:
        prompt = f'''Give me news articles seperataly on both {selected_companies[0]} and {selected_companies[1]} 
        published between {start_date} and {end_date}. 
        All the articles must be relevant to someone who wishes to invest in these companies. 
        All the articles must also have their website link and publishing date if possible.
        '''

        
    elif len(selected_companies) == 1:
        prompt = f'''Give me news articles on {company} published between {start_date} and {end_date}. 
                All the articles must be relevant to someone who wishes to invest in these companies. 
                All the articles must also have their website link and publishing date if possible.
                ''' 
        
    else:
        prompt = ""
        

    if prompt != "":
        # Call the chatbot backend API
        headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
        response = requests.post('http://0.0.0.0:8080/api/chat', json={"query": prompt},headers=headers)

        if response.ok:
            bot_response = response.json().get('response', 'Sorry, I did not understand that.')
            
            st.write(bot_response)
        else:
            st.write(response.text)
            st.error("Error: Unable to get response from the API.")


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
