import streamlit as st
import pyodbc
import psycopg2
from langchain.agents import initialize_agent, AgentType, AgentExecutor
from langchain.memory import ConversationSummaryBufferMemory
from langchain.tools import Tool
from langchain_ollama import ChatOllama
# ------------------------
# Streamlit UI
# ------------------------
st.set_page_config(page_title="Ollama Multi-DB SQL Agent", layout="wide")
st.title("🤖 Ollama Multi-DB SQL Agent")
st.caption("Queries MSSQL & PostgreSQL separately using Ollama.")

# ------------------------
# Sidebar Inputs
# ------------------------
st.sidebar.header("🔗 Database Connections")

# MSSQL
mssql_server = st.sidebar.text_input("MSSQL Server", value="localhost")
mssql_database = st.sidebar.text_input("MSSQL Database", value="abc")
mssql_driver = st.sidebar.text_input("ODBC Driver", value="{ODBC Driver 17 for SQL Server}")
mssql_auth = st.sidebar.radio("MSSQL Authentication", ["Windows", "SQL Login"], index=0)

if mssql_auth == "SQL Login":
    mssql_user = st.sidebar.text_input("MSSQL Username", value="sa")
    mssql_password = st.sidebar.text_input("MSSQL Password", type="password")
    mssql_conn_str = (
        f"DRIVER={mssql_driver};SERVER={mssql_server};DATABASE={mssql_database};UID={mssql_user};PWD={mssql_password};"
    )
else:
    mssql_conn_str = (
        f"DRIVER={mssql_driver};SERVER={mssql_server};DATABASE={mssql_database};Trusted_Connection=yes;"
    )

if st.sidebar.button("Test MSSQL Connection"):
    try:
        conn = pyodbc.connect(mssql_conn_str)
        conn.close()
        st.sidebar.success("✅ MSSQL Connection successful!")
    except Exception as e:
        st.sidebar.error(f"❌ MSSQL Connection failed: {e}")

# PostgreSQL
st.sidebar.markdown("---")
st.sidebar.subheader("PostgreSQL")
pg_host = st.sidebar.text_input("Host", value="localhost")
pg_port = st.sidebar.text_input("Port", value="5432")
pg_database = st.sidebar.text_input("Database", value="purchase_db")
pg_user = st.sidebar.text_input("Username", value="postgres")
pg_password = st.sidebar.text_input("Password", type="password")

# Define as a dictionary for more reliable connection handling
pg_conn_params = {
    "host": pg_host,
    "port": pg_port,
    "dbname": pg_database,
    "user": pg_user,
    "password": pg_password
}
pg_conn_str = f"host={pg_host} port={pg_port} dbname={pg_database} user={pg_user} password={pg_password}"

if st.sidebar.button("Test PostgreSQL Connection"):
    try:
        # Use keyword arguments instead of a connection string for better reliability
        conn = psycopg2.connect(**pg_conn_params)
        conn.close()
        st.sidebar.success("✅ PostgreSQL Connection successful!")
    except Exception as e:
        st.sidebar.error(f"❌ PostgreSQL Connection failed: {e}")

# Ollama Cloud API
st.sidebar.markdown("---")
# ollama_api_key = st.sidebar.text_input("🔑 Ollama Cloud API Key", type="password", key="ollama_key")
# if not ollama_api_key:
#     st.warning("Please enter your Ollama Cloud API key.", icon="⚠️")
#     st.stop()

# ------------------------
# Initialize LLM
# ------------------------
llm = ChatOllama(
    model="gemma4",
    temperature=0,
    base_url="https://ollama.com",
    client_kwargs={
        "headers": {
            "Authorization": f"Bearer {"e4072b94ca9b40a389134d5b6f2956f4.5xqLlcPLBEkWEKSy96yq7YZQ"}"
        }
    }
)

# ------------------------
# Database Query Functions
# ------------------------
def get_mssql_metadata():
    """Get table and column metadata from MSSQL"""
    try:
        conn = pyodbc.connect(mssql_conn_str)
        cursor = conn.cursor()
        query = """
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c 
            ON t.TABLE_NAME = c.TABLE_NAME 
            AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        metadata = {}
        for schema, table, column, dtype in rows:
            key = f"{schema}.{table}"
            if key not in metadata:
                metadata[key] = []
            metadata[key].append(f"{column} ({dtype})")
        
        result = "MSSQL Database Metadata:\n"
        for table, columns in metadata.items():
            result += f"\n{table}:\n  - " + "\n  - ".join(columns) + "\n"
        return result
    except Exception as e:
        return f"Error fetching MSSQL metadata: {str(e)}"

def get_pg_metadata():
    """Get table and column metadata from PostgreSQL"""
    try:
        conn = psycopg2.connect(pg_conn_str)
        cursor = conn.cursor()
        query = """
        SELECT 
            table_schema,
            table_name,
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        metadata = {}
        for schema, table, column, dtype in rows:
            key = f"{schema}.{table}"
            if key not in metadata:
                metadata[key] = []
            metadata[key].append(f"{column} ({dtype})")
        
        result = "PostgreSQL Database Metadata:\n"
        for table, columns in metadata.items():
            result += f"\n{table}:\n  - " + "\n  - ".join(columns) + "\n"
        return result
    except Exception as e:
        return f"Error fetching PostgreSQL metadata: {str(e)}"

def run_mssql_query(query: str):
    """Prepares and returns a formatted MSSQL query."""
    return f"**Database:** MSSQL\n**Query:**\n```sql\n{query}\n```"

def run_pg_query(query: str):
    """Prepares and returns a formatted PostgreSQL query."""
    return f"**Database:** PostgreSQL\n**Query:**\n```sql\n{query}\n```"

def execute_mssql_query(query):
    """Executes a query on MSSQL and returns results as a string"""
    try:
        conn = pyodbc.connect(mssql_conn_str)
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        results = cursor.fetchall()
        conn.close()
        if not results:
            return "No results found."
        
        output = "\n" + " | ".join(columns) + "\n" + "-" * 40 + "\n"
        for row in results:
            output += " | ".join(map(str, row)) + "\n"
        return output
    except Exception as e:
        return f"Error executing MSSQL query: {e}"

def execute_pg_query(query):
    """Executes a query on PostgreSQL and returns results as a string"""
    try:
        conn = psycopg2.connect(**pg_conn_params)
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        results = cursor.fetchall()
        conn.close()
        if not results:
            return "No results found."
        
        output = "\n" + " | ".join(columns) + "\n" + "-" * 40 + "\n"
        for row in results:
            output += " | ".join(map(str, row)) + "\n"
        return output
    except Exception as e:
        return f"Error executing PostgreSQL query: {e}"

# ------------------------
# Define Tools
# ------------------------
tools = [
    Tool(
        name="Get_MSSQL_Metadata",
        func=lambda _: get_mssql_metadata(),
        description="Fetches MSSQL table and column metadata. Use this first to see available MSSQL tables. Input: empty string."
    ),
    Tool(
        name="Get_PostgreSQL_Metadata",
        func=lambda _: get_pg_metadata(),
        description="Fetches PostgreSQL table and column metadata. Use this first to see available PostgreSQL tables. Input: empty string."
    ),
    Tool(
        name="MSSQL_Query_Tool",
        func=lambda q: run_mssql_query(q),
        description="Prepares a SQL query for the MSSQL database. Use this to generate the query. Input: a valid SQL query."
    ),
    Tool(
        name="Postgres_Query_Tool",
        func=lambda q: run_pg_query(q),
        description="Prepares a SQL query for the PostgreSQL database. Use this to generate the query. Input: a valid SQL query."
    ),
    Tool(
        name="Execute_MSSQL_Query",
        func=execute_mssql_query,
        description="Executes a prepared MSSQL query and returns the actual data results. Input: a valid SQL query."
    ),
    Tool(
        name="Execute_Postgres_Query",
        func=execute_pg_query,
        description="Executes a prepared PostgreSQL query and returns the actual data results. Input: a valid SQL query."
    ),
]

# ------------------------
# Initialize Agent with Memory
# ------------------------
if "memory" not in st.session_state:
    st.session_state.memory = ConversationSummaryBufferMemory(
        llm=llm,
        max_token_limit=1024,
        memory_key="chat_history",
        return_messages=True
    )

# Define a concise system prompt
system_prompt = """
You are an expert SQL assistant for two databases: MSSQL and PostgreSQL. Your goal is to answer user questions by generating, executing, and synthesizing data from these databases.

**Crucial Capability: Cross-Database Data Synthesis**
You can satisfy requirements that span across both databases by:
1.  **Executing Multiple Queries:** Run queries on MSSQL and PostgreSQL separately to gather all necessary pieces of information (e.g., get Suppliers from MSSQL and Customers from PostgreSQL).
2.  **Local Data Join:** Since you cannot perform a SQL JOIN across different database engines, you must act as the "Integration Layer". Take the results returned from both execution tools, find common identifiers (like IDs or Names), and combine the data manually in your final response.
3.  **Iterative Retrieval:** If a user asks for "Orders for a specific Supplier", first find the Supplier ID from one DB, then use that ID to query the Orders table in the other DB.

**Workflow:**
1.  **Check Metadata First:** For every new question, use `Get_MSSQL_Metadata` and `Get_PostgreSQL_Metadata` to see available tables.
2.  **Analyze and Plan:** Determine if the answer requires data from one or both databases.
3.  **Execute and Get Data:** Use `Execute_MSSQL_Query` and/or `Execute_Postgres_Query` to fetch the raw data.
4.  **Synthesize and Format:** Process the fetched data based on user requirements. If the user wants a combined view, create a merged table or a detailed summary in your final answer.
5.  **Satisfy User Requirements:** Provide a natural language answer. If the user asks for the queries used, include them, but the priority is the final synthesized result.
6.  **Use History:** Use `chat_history` to maintain context across turns.

You have access to the following tools:
"""

agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    memory=st.session_state.memory,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"system_message": system_prompt}
)

# ------------------------
# Chat UI
# ------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask a question about your databases..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            response = agent_executor.invoke(input=prompt)
            final_result = response.get("output", "No output returned.")
            st.markdown(final_result)
            st.session_state.messages.append({"role": "assistant", "content": final_result})
