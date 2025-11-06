from agent_framework.observability import setup_observability
from telemetry import Langfuse
import httpx
import os
from settings import AUBREY_SETTINGS

os.environ["REQUESTS_CA_BUNDLE"] = "novant_ssl.cer"


def initiate_telemetry():
    # Setup Langfuse observability
    try:
        # Create httpx client with custom SSL certificate for Langfuse
        httpx_client = httpx.Client(verify="novant_ssl.cer")

        # Initialize Langfuse with custom SSL configuration
        langfuse = Langfuse(
            secret_key=AUBREY_SETTINGS.langfuse_secret_key,
            public_key=AUBREY_SETTINGS.langfuse_public_key,
            host=AUBREY_SETTINGS.langfuse_host,
            httpx_client=httpx_client,
        )

        # Setup observability
        setup_observability(enable_sensitive_data=True)
        print("✅ Observability setup completed!")

        # Verify Langfuse connection
        try:
            if langfuse.auth_check():
                print("✅ Langfuse client authenticated and ready!")
            else:
                print("⚠️  Langfuse authentication failed")
        except Exception as e:
            print(f"⚠️  Langfuse auth check error: {e}")

    except ImportError as e:
        print(f"⚠️  setup_observability not available. Error: {e}")
        print("⚠️  Continuing without observability setup.")
        langfuse = None
