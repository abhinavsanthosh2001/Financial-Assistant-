from typing import TypedDict, List

from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_pymongo import PyMongo
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, END, START
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.tools import TavilySearchResults
from flask import Flask, request, jsonify
import yfinance as yf
import os
from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, request, jsonify, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

os.environ["TAVILY_API_KEY"] = "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"
os.environ['OPENAI_API_KEY'] = "sk-3otWxgTJphwfDrrbidAWhynSUwDxP9FDVdJF2YhJfMT3BlbkFJex5N8igTsrm16kSGjuMUbXwxLRnf9dX9A-cjHVhzUA"
app.config['SECRET_KEY'] = "your_secret_key_here"
app.config["MONGO_URI"] = ("mongodb+srv://finchat:mongo@cluster0.8smto.mongodb.net/data?retryWrites=true&w=majority"
                           "&appName=Cluster0majority")

#AUTH

login_manager = LoginManager(app)

mongo = PyMongo(app)

# Bcrypt for password hashing
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


# Signup route
@app.route('/api/signup', methods=['POST'])
def signup():
    users = mongo.db.users
    username = request.json.get('username')
    password = request.json.get('password')
    print(users)
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    existing_user = users.find_one({'username': username})
    print(existing_user)
    if existing_user:
        return jsonify({"error": "Username already exists"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    users.insert_one({'username': username, 'password': hashed_password})

    return jsonify({"message": "User created successfully"}), 201


# Login route
@app.route('/api/login', methods=['POST'])
def login():
    users = mongo.db.users
    username = request.json.get('username')
    password = request.json.get('password')

    user = users.find_one({'username': username})
    if user and bcrypt.check_password_hash(user['password'], password):
        access_token = create_access_token(identity=username)
        print(access_token)
        return jsonify(access_token=access_token), 200

    return jsonify({"error": "Invalid username or password"}), 401





# Define state schemas
class InputState(TypedDict):
    query: str


class OutputState(TypedDict):
    response: str


class OverallState(MessagesState):
    query: str
    data_source: str
    historical_data: dict
    news_articles: list


# Initialize StateGraph
graph = StateGraph(OverallState, input=InputState, output=OutputState)


# Query Analyzer
def query_analyzer(state: OverallState) -> dict:
    query = state["query"]
    chat = ChatOpenAI(model="gpt-4o")
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Analyze the user query and determine which data source(s) to use. Options are: 'historical_stock', 'news_articles', or 'both'."),
        ("human", "{query}")
    ])
    response = chat.invoke(prompt.format_messages(query=query))
    return {"query": query, "data_source": response.content}


# Historical Stock Data Agent
# def historical_stock_data_agent(state: OverallState) -> dict:
#     query = state["query"]
#     # Extract stock symbol and date range from query
#     # For simplicity, let's assume we're getting Apple stock data for the last 5 years
#     stock_data = yf.Ticker("AAPL").history(period="1mo")
#     print(len(stock_data))
#     return {"historical_data": stock_data.to_dict()}

def historical_stock_data_agent(state: OverallState) -> dict:
    query = state["query"]
    chat = ChatOpenAI(model="gpt-4o")

    # Prompt to analyze the query and extract relevant information
    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", "Analyze the stock-related query and extract the following information:\n"
                   "1. Company stock symbol\n"
                   "2. Start date (if specified)\n"
                   "3. End date (if specified)\n"
                   "4. Any other relevant details (e.g., top N stocks)\n"
                   "If any information is not provided, indicate 'Not specified'. "
                   "Note that for Start date and End date, give the response in the form of YYYY-MM-DD. "
                   "If year or day not specified, assume 2024 and 1 respectively. "
                   "Also, know that current date is 2024-11-17"),
        ("human", "{query}")
    ])

    analysis_response = chat.invoke(analysis_prompt.format_messages(query=query))
    analysis = analysis_response.content

    # Prompt to determine the action based on the analysis
    action_prompt = ChatPromptTemplate.from_messages([
        ("system", "Based on the following analysis of a stock-related query, determine the appropriate action:\n"
                   "1. Fetch historical data for a specific stock\n"
                   "2. Provide recommendations for top stocks to buy\n"
                   # "3. Provide recommendations for a specific stock"
                   "Respond with either '1' or '2' , followed by a brief explanation."
                   ),
        ("human", "{analysis}")
    ])

    action_response = chat.invoke(action_prompt.format_messages(analysis=analysis))
    action = action_response.content

    if action.startswith("1"):
        # Fetch historical data for a specific stock
        company = extract_company(analysis)
        start_date, end_date = extract_dates(analysis)

        # Limit the data range to a maximum of 10 months
        if (end_date - start_date).days > 305:
            start_date = end_date - timedelta(days=305)

        stock_data = fetch_stock_data(company, start_date, end_date)
        return {"historical_data": stock_data.to_dict()}

    elif action.startswith("2"):
        # Provide recommendations for top stocks to buy
        top_stocks = get_top_stocks(10)
        # top_stocks = []
        return {"historical_data": {"top_stocks": top_stocks}}

    elif action.startswith("3"):
        stock = extract_company(analysis)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # Consider 1 year of data

        total_score = "NA"
        try:
            data = yf.Ticker(stock).history(start=start_date, end=end_date)
            if not data.empty:
                recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
                volatility = data['Close'].pct_change().std()
                avg_volume = data['Volume'].mean()

                # Simple scoring system
                growth_score = recent_growth * 100  # Weight growth more heavily
                volatility_score = -volatility * 50  # Lower volatility is better
                volume_score = avg_volume / 1e6  # Normalize volume

                total_score = growth_score + volatility_score + volume_score

        except Exception as e:
            print(f"Error fetching data for {stock}: {e}")

        return {"historical_data": {"recommendation_score": total_score}}


    else:
        return {"historical_data": {"error": "Unable to process the query"}}


def extract_company(analysis):
    # Extract company name or stock symbol from the analysis
    # This is a simplified version; you might want to use regex or more sophisticated NLP
    lines = analysis.split('\n')
    for line in lines:
        if line.startswith("1. Company name or stock symbol:"):
            return line.split(":")[1].strip()
    return "AAPL"  # Default to Apple if not found


def extract_dates(analysis):
    # Extract start and end dates from the analysis
    start_date = datetime.now() - timedelta(days=365)  # Default to 1 year ago
    end_date = datetime.now()

    lines = analysis.split('\n')
    for line in lines:
        if line.startswith("2. Start date:"):
            start_str = line.split(":")[1].strip()
            if start_str != "Not specified":
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
        elif line.startswith("3. End date:"):
            end_str = line.split(":")[1].strip()
            if end_str != "Not specified":
                end_date = datetime.strptime(end_str, "%Y-%m-%d")

    return start_date, end_date


def fetch_stock_data(company, start_date, end_date):
    # Fetch stock data using yfinance
    stock = yf.Ticker(company)
    data = stock.history(start=start_date, end=end_date)
    return data


def get_top_stocks(total_number):

    return []

    stocks = ["AAPL", "MSFT", "AMZN", "GOOGL", "FB", "TSLA", "NVDA", "JPM", "V", "JNJ",
              "WMT", "PG", "DIS", "NFLX", "ADBE", "CRM", "PYPL", "INTC", "CSCO", "VZ"]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # Consider 1 year of data

    stock_data = {}
    for stock in stocks:
        try:
            data = yf.Ticker(stock).history(start=start_date, end=end_date)
            if not data.empty:
                stock_data[stock] = data
        except Exception as e:
            print(f"Error fetching data for {stock}: {e}")

    results = []
    for stock, data in stock_data.items():
        if len(data) > 0:
            # Calculate metrics
            recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
            volatility = data['Close'].pct_change().std()
            avg_volume = data['Volume'].mean()

            # Simple scoring system
            growth_score = recent_growth * 100  # Weight growth more heavily
            volatility_score = -volatility * 50  # Lower volatility is better
            volume_score = avg_volume / 1e6  # Normalize volume

            total_score = growth_score + volatility_score + volume_score

            results.append((stock, total_score))

    # Sort stocks by total score in descending order
    results.sort(key=lambda x: x[1], reverse=True)

    # Return the top N stocks
    return [stock for stock, _ in results[:total_number]]

# News Article Agent
def news_article_agent(state: OverallState) -> dict:
    query = state["query"]

    # for specific stock recommendation, change max_results from 10 to 1
    # search = TavilySearchResults(max_results=10)
    search = TavilySearchResults()
    results = search.invoke(query)
    # print(len(results))
    # try:
    #     {"news_articles": results[:10]}
    # except:
    #     return {"news_articles": results}
    return {"news_articles": results[:10]}

    query = state["query"]
    chat = ChatOpenAI(model="gpt-4o")


    action_prompt = ChatPromptTemplate.from_messages([
        ("system", "Analyse the query if give the response as 'Specific' if the user is asking for stock "
                   "recommendation of a specific company"),
        ("human", f"Query: {query}\n")
    ])

    action_response = chat.invoke(action_prompt.format_messages(query=query))
    action = action_response.content

    if action.startswith('Specific'):
        search = TavilySearchResults(max_results=2)
        results = search.invoke(query)
        print(len(results))

        return {"news_articles": results[:2]}

    search = TavilySearchResults(max_results=10)
    results = search.invoke(query)
    print(len(results))

    return {"news_articles": results[:10]}


# RAG Agent
def rag_agent(state: OverallState) -> OutputState:
    chat = ChatOpenAI(model="gpt-4o")
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Generate a concise and accurate response based on the provided data. "
         "In case of citing news articles, include the URL to the articles. "
         "In case of historical data, show the data in the form of a table. "
         "In case of stocks recommendation, include BOTH the historical data analysis AND relevant recent news "
         "articles."
         "Mention to use Analytics page for graphical representation of historical data if the response mentions "
         "historical data."
         "Include citations for the information used."
         ),
        ("human", "{query}"),
        ("system", "Historical Data: {historical_data}"),
        ("system", "News Articles: {news_articles}")
    ])

    response = chat.invoke(prompt.format_messages(
        query=state.get("query"),
        historical_data=state.get("historical_data", "N/A"),
        news_articles=state.get("news_articles", "N/A")
    ))

    return {"response": response.content}


# Add nodes to the graph
graph.add_node("query_analyzer", query_analyzer)
graph.add_node("historical_stock_data", historical_stock_data_agent)
graph.add_node("news_articles_data", news_article_agent)
graph.add_node("rag_agent", rag_agent)


# Router function
def router(state: OverallState):
    data_source = state["data_source"]
    if data_source == "historical_stock":
        return "historical_stock_data"
    elif data_source == "news_articles":
        return "news_articles_data"
    else:
        return ["historical_stock_data", "news_articles_data"]


# Connect the nodes
graph.add_edge(START, "query_analyzer")
graph.add_conditional_edges("query_analyzer", router)
graph.add_edge("historical_stock_data", "rag_agent")
graph.add_edge("news_articles_data", "rag_agent")
graph.add_edge("rag_agent", END)

# Compile the graph
chain = graph.compile()


# Chatbot function

def chatbot(query: str) -> str:
    result = chain.invoke({"messages": [HumanMessage(content=query)], "query": query})
    # If historical data is present in the result, format it for better readability
    if "historical_data" in result and isinstance(result["historical_data"], dict):
        if "top_stocks" in result["historical_data"]:
            top_stocks = result["historical_data"]["top_stocks"]
            formatted_stocks = "\n".join(f"{i + 1}. {stock}" for i, stock in enumerate(top_stocks))
            result["response"] += f"\n\nTop 10 stocks recommended:\n{formatted_stocks}"
        elif "Open" in result["historical_data"]:
            df = pd.DataFrame(result["historical_data"])
            result["response"] += f"\n\nHistorical Data Summary:\n{df.describe().to_string()}"

    return result["response"]


# API endpoint
@app.route('/api/chat', methods=['POST'])
@jwt_required()
def chatbot_api():
    current_user = get_jwt_identity()
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        response = chatbot(query)
        return jsonify({"response": response, "user": current_user})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)

    # queries = [
    #     "Give me the microsoft stock prices data from 2015-01-01 to 2018-12-31.",
    #     "Give me all the latest news articles of Apple.",
    #     "What are top 10 stocks that I can buy right now?",
    # ]
    #
    # for query in queries:
    #     print(f"Query: {query}")
    #     response = chatbot(query)
    #     print(f"Response: {response}\n")