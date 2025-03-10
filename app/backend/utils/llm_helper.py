import ollama
import json
import re
from typing import List, Dict, Any, Optional, Union
from backend.config import Config
from backend.utils.redis_manager import RedisManager
from backend.utils.vector_store import VectorStoreManager
from backend.utils.web_search import WebSearchAgent

system_prompt = Config.SYSTEM_PROMPT
# Set Ollama host to connect to Kubernetes service via NodePort
ollama.host = f"http://{Config.OLLAMA_HOST}:{Config.OLLAMA_PORT}"

def tool_selection_prompt(user_query: str) -> str:
    """Create a prompt to ask the LLM which tool to use"""
    return f"""# Tool Selection Agent

You are an advanced tool selection agent. You will analyze the user query and select the most appropriate tool to handle it. You must choose exactly one of the three available tools for each query. This is mission critical. Think thoroughly about the tool you will be choosing and the query value you will be passing to it. The query you will be passing is as important as tool selection as it decides your answer.

## Tools
1. **calculator**: Use for any mathematical question (simple or complex), including word problems that require calculation. Always use this for calculations even if they seem trivial. This is based on Python shell execution so provide equations, not words.

2. **web_search**: Use for factual or current information needs (e.g., "Latest SpaceX rocket launch", "Population of France").

3. **none**: Use to directly answer simple questions based on general knowledge or conversation history that don't require calculations or searching for current information.

## Response Format
For every user query, respond in this format:

```json
{{
  "tool": "selected_tool_name",
  "reasoning": "Brief explanation of why this tool was selected",
  "parameters": {{"query": "formatted_query_for_tool"}}
}}
```

Keep your reasoning concise (2-3 sentences maximum).

## Examples

### Example 1: Simple Calculation
User Query: "What is 15 plus 27?"

```json
{{
  "tool": "calculator",
  "reasoning": "This is a basic addition problem. Even though it's simple, I should use the calculator tool for all mathematical operations.",
  "parameters": {{"query": "15 + 27"}}
}}
```

### Example 2: Basic Word Problem
User Query: "If I have 3 dozen eggs and use 5 eggs to make a cake, how many eggs do I have left?"

```json
{{
  "tool": "calculator",
  "reasoning": "This requires converting dozens to individual eggs and then subtracting. It's a mathematical word problem that needs calculation.",
  "parameters": {{"query": "(3 * 12) - 5"}}
}}
```

### Example 3: Complex Word Problem
User Query: "A train leaves Chicago at 2:30 PM traveling at 65 mph. Another train leaves Denver at 3:15 PM traveling at 70 mph in the opposite direction. If Chicago and Denver are 996 miles apart, at what time will the trains pass each other?"

```json
{{
  "tool": "calculator",
  "reasoning": "This is a complex relative motion problem requiring calculation of when two trains meet. I need to set up an equation based on distance, speed, and time.",
  "parameters": {{"query": "996 / (65 + 70) + (3.25 - 2.5)"}}
}}
```

### Example 4: Multi-step Financial Calculation
User Query: "I'm investing $10,000 in a fund that returns 7% annually, compounded monthly. After 5 years, I add another $5,000. How much will I have after 10 years total?"

```json
{{
  "tool": "calculator",
  "reasoning": "This requires compound interest calculations in two phases: the initial investment for 10 years and the additional investment for 5 years.",
  "parameters": {{"query": "10000 * (1 + 0.07/12)**(12*10) + 5000 * (1 + 0.07/12)**(12*5)"}}
}}
```

### Example 5: Percentage and Proportion Problem
User Query: "A recipe calls for 2¾ cups of flour to make 24 cookies. If I want to make 36 cookies but only have 3½ cups of flour, what percentage more flour do I need?"

```json
{{
  "tool": "calculator",
  "reasoning": "This involves proportions, fractions, and percentage calculations. I need to determine required flour, compare to available flour, and express the difference as a percentage.",
  "parameters": {{"query": "((2.75 * (36/24) - 3.5) / 3.5) * 100"}}
}}
```

### Example 6: Simple Factual Query
User Query: "Who is the current president of South Korea?"

```json
{{
  "tool": "web_search",
  "reasoning": "This is a request for current factual information about political leadership that may change over time.",
  "parameters": {{"query": "current president of South Korea 2024"}}
}}
```

### Example 7: Complex Factual Query
User Query: "What are the primary differences between CRISPR-Cas9 and the newer CRISPR-Cas12a gene editing technologies?"

```json
{{
  "tool": "web_search",
  "reasoning": "This requires specific and technical scientific information about evolving gene editing technologies. Current detailed comparisons would be available through search.",
  "parameters": {{"query": "differences between CRISPR-Cas9 and CRISPR-Cas12a gene editing technologies comparison"}}
}}
```

### Example 8: General Knowledge
User Query: "What is the meaning of life?"

```json
{{
  "tool": "none",
  "reasoning": "This is a philosophical question that doesn't require calculation or current information, so I can answer directly.",
  "parameters":{{"query": ""}}
}}
```

## Important Notes
- ALWAYS use the calculator tool for ANY mathematical question, no matter how simple it may seem.
- For word problems, extract the mathematical operation needed and format it as an equation.
- The calculator uses Python syntax, so ensure expressions are properly formatted.
- When in doubt between web_search and none, choose web_search for specific factual information that might change over time.

# Current Query
"{user_query}"
"""

def evaluate_expression(expression: str) -> str:
    """Safely evaluate a math expression"""
    try:
        # Clean the expression to only allow safe operations
        # Only allow digits, basic operators, parentheses, and whitespace
        cleaned_expr = re.sub(r'[^0-9+\-*/().%\s]', '', expression)
        if not cleaned_expr:
            return "Invalid mathematical expression"
            
        # Evaluate the expression
        result = eval(cleaned_expr)
        return f"Expression: {expression}\nResult: {result}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"

def execute_tool(tool_name: str, parameters: Dict[str, Any], session_id: str, status_callback=None) -> str:
    """Execute tool with session context and provide status updates"""
    # Default status callback if none provided
    if status_callback is None:
        def status_callback(message):
            pass
    
    # No initial status here - this will be handled by the caller
    
    if tool_name == "calculator":
        status_callback("➗ Calculating...")
        
        expression = parameters.get("query", "")
        if not expression:
            return "No mathematical expression provided."
        
        result = evaluate_expression(expression)
        
        status_callback("✅ Calculation complete!")
        return result
        
    elif tool_name == "web_search":
        status_callback("🌐 Launching web search operation...")
        
        web_agent = WebSearchAgent()
        vector_store = VectorStoreManager()
        query = parameters["query"]
        
        # First, perform the web search
        web_results = web_agent.search(query)
        
        # Extract sources for status message
        sources = [result["source"] for result in web_results]
        if sources:
            source_list = ", ".join(sources[:3])
            if len(sources) > 3:
                source_list += f", and {len(sources) - 3} more sources"
            status_callback(f"📑 Extracting relevant information from sources: {source_list}")
        else:
            status_callback(f"📑 No sources found. Generating answer from LLM without context...")
    
        # Store in vector DB with session_id for filtering
        if sources:
            vector_store.store_documents(web_results, session_id=session_id)
        
        # Retrieve relevant chunks - filtered by session ID
        rag_results = vector_store.search(query, session_id=session_id)

        # Clean up the documents immediately after search
        vector_store.delete_session_embeddings(session_id)
        
        status_callback("✅ Information processing complete!")
        
        if not rag_results:
            return "No relevant information found."
            
        formatted_results = ""
        for i, result in enumerate(rag_results, 1):
            formatted_results += f"Result {i}:\n{result['text']}\nSource: {result['source']}\n\n"
        
        return formatted_results
    
    else:
        return "No tool executed."

def parse_tool_selection(response: str) -> Dict:
    """Parse the LLM's tool selection response"""
    try:
        json_str = response.strip()

        # Extract JSON from markdown code blocks
        if "```json" in json_str:
            # Handle ```json ... ``` blocks
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            # Handle ``` ... ``` blocks (non-JSON specified)
            json_str = json_str.split("```")[1].split("```")[0].strip()

        # Find the outermost JSON object
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            raise ValueError("No valid JSON object found")

        json_str = json_str[start_idx:end_idx+1].strip()
        parsed = json.loads(json_str)

        # Ensure parameters exist
        parsed.setdefault("parameters", {})

        # Set default parameters based on tool
        tool = parsed.get("tool")
        params = parsed["parameters"]

        if tool == "calculator":
            if "query" not in params:
                params["query"] = params.get("query", "")
        elif tool == "web_search":
            # Ensure 'query' is present
            params.setdefault("query", "")

        return parsed
    except Exception as e:
        print(f"Error parsing tool selection: {e}")
        return {"tool": "none", "parameters": {"query": ""}}

def select_tool(model: str, user_query: str):
    """Ask the LLM which tool to use for a given query"""
    tool_prompt = tool_selection_prompt(user_query)
    tool_messages = [{"role": "system", "content": system_prompt}]
    tool_messages.append({"role": "user", "content": tool_prompt})
    
    tool_response = ollama.chat(
        model=model,
        messages=tool_messages,
        stream=False,
    )
    
    return parse_tool_selection(tool_response["message"]["content"])

def generate_response(model: str, tool_context: Optional[str] = None):
    """Generate final response with optional tool context"""    
    # Get the response stream
    stream = ollama.chat(
        model=model,
        messages=tool_context,
        stream=True,
        options={
            "num_ctx": 4096
        } 
    )
    
    return stream

# Stream parser to handle different response formats
def stream_parser(stream):
    for chunk in stream:
        yield chunk['message']['content']