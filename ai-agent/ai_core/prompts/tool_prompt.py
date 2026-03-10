"""
Tool Calling Prompt Templates
"""


TOOL_CALL_PROMPT = """
You have access to the following tools:

{tool_descriptions}

When a tool is required:
- Respond in JSON format.
- Use the structure:

{
    "tool_name": "<tool_name>",
    "arguments": { ... }
}

If no tool is needed:
- Answer normally.
"""


TOOL_RESPONSE_PROMPT = """
The tool returned the following result:

{tool_result}

Now:
- Use this information to answer the user.
- Do not mention the tool explicitly.
- Provide a final helpful response.
"""