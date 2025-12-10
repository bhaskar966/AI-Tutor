from google.genai import types

# Shared retry configuration for all agents
# Configured with increased attempts to handle potential rate limits (429) gracefully.
retry_config = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(initial_delay=2, attempts=15)
    )
)
