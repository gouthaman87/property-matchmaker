import time
import hashlib
import pandas as pd
from langchain_groq import ChatGroq
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent


class PropertyMatchmaker:
    """A real estate property search agent powered by LangChain and Groq (free tier).

    Free tier limits (Groq):
      - 30 requests/minute
      - 14,400 requests/day
      - 131,072 tokens per request
    """

    def __init__(self, data_path: str = "data/Central7_DB_20260218.xlsx", model: str = "llama-3.3-70b-versatile", temperature: float = 0):
        # model: str = "llama-3.3-70b-versatile"  # Original model (commented out — daily token limit exhausted)
        # 1. Load the Excel database
        self.df = pd.read_excel(data_path, sheet_name=1)

        # 2. Initialize the AI (uses GROQ_API_KEY env variable)
        self.llm = ChatGroq(
            model=model,
            temperature=temperature,
            max_retries=3,
        )

        # 3. Create the Agent — limit head rows to reduce token usage on large datasets
        self.agent = create_pandas_dataframe_agent(
            self.llm,
            self.df,
            verbose=False,
            allow_dangerous_code=True,
            number_of_head_rows=2,
            max_iterations=20,
            early_stopping_method="generate",
            prefix=(
                "You are working with a pandas dataframe called `df` with "
                f"{len(self.df)} rows and {len(self.df.columns)} columns.\n"
                "IMPORTANT: The dataframe is large. Never try to print the entire dataframe. "
                "Always use filtering, .head(), or .query() to limit results. "
                "Use df.columns to see column names and df.dtypes to understand types.\n"
                "When you have enough information to answer, return the final answer immediately."
            ),
        )

        # 4. Simple cache & rate limit tracking
        self._cache: dict[str, str] = {}
        self._request_times: list[float] = []

    def _rate_limit(self, max_rpm: int = 10):
        """Enforce rate limit to stay well under 15 RPM free tier."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= max_rpm:
            wait = 60 - (now - self._request_times[0])
            if wait > 0:
                print(f"⏳ Rate limit: waiting {wait:.1f}s to stay in free tier...")
                time.sleep(wait)
        self._request_times.append(time.time())

    def search_properties(self, user_query: str, max_retries: int = 3) -> str:
        """Search the database for properties matching the user's requirements."""
        # Check cache first to avoid duplicate API calls
        cache_key = hashlib.md5(user_query.strip().lower().encode()).hexdigest()
        if cache_key in self._cache:
            print("✅ Returning cached result (no API call used)")
            return self._cache[cache_key]

        # Rate limit before calling
        self._rate_limit()

        # system_prompt = (
        #     "You are a professional real estate agent. Look at the database and "
        #     "find properties that match the user's requirements. "
        #     "If a specific requirement (like a pool) isn't met exactly, suggest the closest match. "
        #     "Always return the Ref No, Address, Size, Price, and a short 'Why it fits' summary for each matching property."
        # )
        system_prompt = (
            "You are a smart property search agent. Your goal is to find the right match of properties based on the user's query. "
            "Queries may not be structured properly, therefore use your intelligence to understand the query well. "
            "Determine if the request is for sale or rent. "
            # Feel free to ask clarifying questions if needed. "
            "Find properties that match the query and pick only the active ones. "
            "If a specific requirement (like a pool) isn't met exactly, suggest the closest match. "
            "Always return the Ref No, Location/Building Name, Size, No of Bedrooms, Price, and a short 'Why it fits' summary for each matching property."
        )

        # Retry with exponential backoff for rate limit errors
        for attempt in range(max_retries):
            try:
                response = self.agent.invoke(f"{system_prompt}\n\nUser Request: {user_query}")
                result = response["output"]
                # Cache the result
                self._cache[cache_key] = result
                return result
            except Exception as e:
                err_str = str(e).lower()
                print(f"⚠️ Attempt {attempt + 1}/{max_retries} error: {str(e)[:200]}")
                if "429" in err_str or "rate" in err_str or "resource_exhausted" in err_str:
                    wait = (attempt + 1) * 40
                    print(f"⏳ Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

        return "❌ Could not complete search — rate limit exceeded. Please try again in a few minutes."