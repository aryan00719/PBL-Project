import os

# Render sets the PORT environment variable.
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Render Free Tier has 512MB RAM and 0.1 CPU
# Keep workers at 1 to prevent Out-Of-Memory (OOM) errors.
workers = 1

# Using threads can handle concurrent requests better in a single worker
threads = 4

# Increase timeout since some initial map rendering/loading can take time
timeout = 120
