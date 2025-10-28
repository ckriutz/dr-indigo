# Use Python 3.12 slim image as base
FROM python:3.12

# Set working directory in container
WORKDIR /code

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application code
COPY api.py .
COPY medical_triage_agent.py .
COPY joint_surgery_info_agent.py .
COPY GuideToTotalJointSurgery_ENG_V2.pdf .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]