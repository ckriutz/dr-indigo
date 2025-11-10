import os
from pathlib import Path

import httpx
from agent_framework.observability import setup_observability
from langfuse import Langfuse

from settings import AUBREY_SETTINGS

CERT_PATH = Path(__file__).with_name("novant_ssl.cer")


def initiate_telemetry():
    cert_available = CERT_PATH.exists()
    secrets_available = all(
        (
            AUBREY_SETTINGS.langfuse_secret_key,
            AUBREY_SETTINGS.langfuse_public_key,
            AUBREY_SETTINGS.langfuse_host,
        )
    )

    if not cert_available or not secrets_available:
        missing_items = []
        if not cert_available:
            missing_items.append(f"SSL certificate at {CERT_PATH}")
        if not AUBREY_SETTINGS.langfuse_secret_key:
            missing_items.append("AUBREY_SETTINGS.langfuse_secret_key")
        if not AUBREY_SETTINGS.langfuse_public_key:
            missing_items.append("AUBREY_SETTINGS.langfuse_public_key")
        if not AUBREY_SETTINGS.langfuse_host:
            missing_items.append("AUBREY_SETTINGS.langfuse_host")

        print("⚠️  Langfuse observability setup skipped. Missing:")
        for item in missing_items:
            print(f"   - {item}")
        print("⚠️  Continuing without observability.")
        return

    os.environ["REQUESTS_CA_BUNDLE"] = str(CERT_PATH)

    # Setup Langfuse observability
    try:
        # Create httpx client with custom SSL certificate for Langfuse
        httpx_client = httpx.Client(verify=str(CERT_PATH))

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
