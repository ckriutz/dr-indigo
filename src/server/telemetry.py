from agent_framework.observability import setup_observability
from langfuse import Langfuse
import httpx
import os
from settings import AUBREY_SETTINGS


def initiate_telemetry():
    """
    Initialize Langfuse telemetry and observability.
    
    Checks for required settings and SSL certificate before attempting setup.
    If any requirements are missing, prints what's missing and skips setup.
    """
    # Get absolute path to SSL certificate
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    CERT_PATH = os.path.join(SCRIPT_DIR, "novant_ssl.cer")
    
    # Check for required settings
    missing_items = []
    
    if not AUBREY_SETTINGS.langfuse_secret_key:
        missing_items.append("AUBREY_SETTINGS.langfuse_secret_key")
    
    if not AUBREY_SETTINGS.langfuse_public_key:
        missing_items.append("AUBREY_SETTINGS.langfuse_public_key")
    
    if not AUBREY_SETTINGS.langfuse_host:
        missing_items.append("AUBREY_SETTINGS.langfuse_host")
    
    if not os.path.exists(CERT_PATH):
        missing_items.append(f"SSL certificate at {CERT_PATH}")
    
    # If anything is missing, print and skip setup
    if missing_items:
        print("⚠️  Langfuse observability setup skipped. Missing:")
        for item in missing_items:
            print(f"   - {item}")
        print("⚠️  Continuing without observability.")
        return
    
    # All requirements present, proceed with setup
    try:
        
        # Configure SSL for OpenTelemetry span exporter
        os.environ["OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE"] = CERT_PATH
        #os.environ["REQUESTS_CA_BUNDLE"] = CERT_PATH

        # Create HTTPX client with certificate for Langfuse API requests
        httpx_client = httpx.Client(verify=CERT_PATH)
        
        # Initialize Langfuse with custom SSL configuration
        langfuse = Langfuse(
            secret_key=AUBREY_SETTINGS.langfuse_secret_key,
            public_key=AUBREY_SETTINGS.langfuse_public_key,
            host=AUBREY_SETTINGS.langfuse_host,
            httpx_client=httpx_client,
        )

        # Verify Langfuse connection
        if langfuse.auth_check():
            print("✅ Langfuse client authenticated and ready!")
        else:
            print("⚠️  Langfuse authentication failed")
        
        # Setup observability
        setup_observability(enable_sensitive_data=True)
        print("✅ Observability setup completed!")
        
            
    except Exception as e:
        print(f"⚠️  Error during Langfuse setup: {e}")
        print("⚠️  Continuing without observability.")
