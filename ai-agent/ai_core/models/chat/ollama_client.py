import requests
import time
import threading
from typing import Dict, Any, List, Union, Optional

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except:
    tracer = None


# ============================================================
# CIRCUIT BREAKER
# ============================================================

class CircuitBreaker:

    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

        self._lock = threading.Lock()

    def call_allowed(self):

        with self._lock:

            if self.state == "OPEN":

                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True

                return False

            return True

    def record_success(self):

        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self):

        with self._lock:

            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"


# ============================================================
# OLLAMA CLIENT
# ============================================================

class OllamaClient:
    """
    Production Ollama Client for LangGraph Agent Systems

    Features
    --------
    - Tool calling
    - Streaming
    - Structured output
    - Retry
    - Circuit breaker
    - Token usage tracking
    - Observability (OpenTelemetry)
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0,
        timeout: int = 120,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        stream: bool = False,
    ):

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.stream = stream

        self.tools = None

        self.breaker = CircuitBreaker()

        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    # ============================================================
    # LANGGRAPH TOOL BINDING
    # ============================================================

    def bind_tools(self, tools):

        """
        Attach tool definitions for LangGraph compatibility.
        """

        self.tools = tools
        return self

    # ============================================================
    # MAIN INVOKE
    # ============================================================

    def invoke(
        self,
        messages: Union[str, List[Dict[str, str]]],
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:

        """
        LangGraph compatible call
        """

        if not self.breaker.call_allowed():
            raise RuntimeError(
                f"Circuit breaker OPEN for model {self.model}"
            )

        payload = self._build_payload(messages, response_format)

        attempt = 0

        while attempt < self.max_retries:

            try:

                if tracer:
                    with tracer.start_as_current_span("ollama.invoke"):
                        response = self._do_request(payload)
                else:
                    response = self._do_request(payload)

                self.breaker.record_success()

                return response

            except Exception as e:

                self.breaker.record_failure()

                if attempt == self.max_retries - 1:
                    raise e

                sleep_time = self.backoff_factor ** attempt
                time.sleep(sleep_time)

                attempt += 1

    # ============================================================
    # HTTP REQUEST
    # ============================================================

    def _do_request(self, payload):

        url = f"{self.base_url}/api/chat"

        if self.stream:

            return self._stream_request(url, payload)

        response = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()

        data = response.json()

        self._track_usage(data)

        return {
            "role": "assistant",
            "content": data["message"]["content"]
        }

    # ============================================================
    # STREAMING
    # ============================================================

    def _stream_request(self, url, payload):

        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=self.timeout
        )

        response.raise_for_status()

        final_text = ""

        for line in response.iter_lines():

            if not line:
                continue

            chunk = line.decode("utf-8")

            try:
                data = eval(chunk)
            except:
                continue

            if "message" in data:

                content = data["message"].get("content", "")

                final_text += content

                print(content, end="", flush=True)

        return {
            "role": "assistant",
            "content": final_text
        }

    # ============================================================
    # BUILD PAYLOAD
    # ============================================================

    def _build_payload(
        self,
        messages: Union[str, List[Dict[str, str]]],
        response_format: Optional[Dict]
    ) -> Dict[str, Any]:

        if isinstance(messages, str):

            messages = [
                {"role": "user", "content": messages}
            ]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": self.stream,
            "options": {
                "temperature": self.temperature
            }
        }

        if self.tools:
            payload["tools"] = self._build_tools_schema()

        if response_format:
            payload["format"] = response_format

        return payload

    # ============================================================
    # TOOL SCHEMA
    # ============================================================

    def _build_tools_schema(self):

        schemas = []

        for tool in self.tools:

            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_schema.schema()
                    if tool.args_schema
                    else {
                        "type": "object",
                        "properties": {}
                    }
                }
            }

            schemas.append(schema)

        return schemas

    # ============================================================
    # TOKEN TRACKING
    # ============================================================

    def _track_usage(self, data):

        usage = data.get("usage")

        if not usage:
            return

        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)

        self.total_prompt_tokens += prompt
        self.total_completion_tokens += completion

    # ============================================================
    # METRICS
    # ============================================================

    def get_usage(self):

        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens
        }