from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Annotated

from agent_framework import AgentExecutor, ChatAgent, ai_function
from agent_framework.azure import AzureOpenAIChatClient
from pydantic import BaseModel, Field


class AuthenticationToolResponse(BaseModel):
    """Represents the outcome returned by the mocked authentication API."""

    status: str = Field(description="One of: success, multiple_matches, not_found, invalid_request.")
    message: str = Field(description="Human readable status message from the authentication service.")
    mrn: str | None = Field(default=None, description="Medical Record Number when authenticated.")
    requires_phone_number: bool = Field(
        default=False,
        description="True when the service needs an additional phone number to disambiguate duplicates.",
    )


def _generate_mrn(first_name: str, last_name: str, date_of_birth: str, phone_number: str | None) -> str:
    """Create a stable mock MRN using a hash of the identifying information."""

    digest_source = f"{first_name.strip().lower()}|{last_name.strip().lower()}|{date_of_birth}|{phone_number or ''}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest().upper()
    return f"MRN-{digest[:4]}-{digest[4:8]}-{digest[8:12]}"


def _should_require_phone(first_name: str, last_name: str, date_of_birth: str) -> bool:
    """Deterministically decide when an extra phone number is required."""

    digest_source = f"{first_name.strip().lower()}|{last_name.strip().lower()}|{date_of_birth}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    # Roughly 20% of combinations trigger a duplicate match scenario.
    return int(digest[:6], 16) % 5 == 0


@ai_function(name="authenticate_patient", description="Authenticate a patient and return their MRN when successful.")
def authenticate_patient(
    first_name: Annotated[str, "Patient's legal first name."],
    last_name: Annotated[str, "Patient's legal last name."],
    date_of_birth: Annotated[str, "Patient date of birth in YYYY-MM-DD format."],
    phone_number: Annotated[str | None, "10-digit phone number including area code (optional)."] = None,
) -> dict:
    """Mocked external API used by the authentication agent."""

    first = first_name.strip()
    last = last_name.strip()
    dob = date_of_birth.strip()

    try:
        datetime.strptime(dob, "%Y-%m-%d")
    except ValueError:
        return AuthenticationToolResponse(
            status="invalid_request",
            message="Date of birth must use YYYY-MM-DD format.",
            requires_phone_number=False,
            mrn=None,
        ).model_dump()

    if not phone_number and _should_require_phone(first, last, dob):
        return AuthenticationToolResponse(
            status="multiple_matches",
            message="Multiple patients matched. A phone number is required to continue.",
            requires_phone_number=True,
            mrn=None,
        ).model_dump()

    if phone_number:
        normalized_phone = "".join(ch for ch in phone_number if ch.isdigit())
        if len(normalized_phone) < 10:
            return AuthenticationToolResponse(
                status="invalid_request",
                message="Phone number must include area code (at least 10 digits).",
                requires_phone_number=True,
                mrn=None,
            ).model_dump()
    else:
        normalized_phone = None

    mrn = _generate_mrn(first, last, dob, normalized_phone)
    return AuthenticationToolResponse(
        status="success",
        message="Patient authenticated successfully.",
        requires_phone_number=False,
        mrn=mrn,
    ).model_dump()


class PatientAuthenticationResult(BaseModel):
    """Structured state returned by the authentication agent each turn."""

    message_to_patient: str = Field(
        description="Natural language message that should be shared with the patient this turn."
    )
    is_authenticated: bool = Field(
        default=False,
        description="True once the patient identity is verified and an MRN is available.",
    )
    requires_phone_number: bool = Field(
        default=False,
        description="True when the authentication service requested a phone number to disambiguate.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="List of patient fields that still need to be collected (first_name, last_name, date_of_birth, phone_number, medical_concern).",
    )
    triage_ready: bool = Field(
        default=False,
        description="True when the patient is authenticated and their medical concern has been captured.",
    )
    mrn: str | None = Field(default=None, description="Patient's medical record number when authenticated.")
    first_name: str | None = Field(default=None, description="Captured patient first name.")
    last_name: str | None = Field(default=None, description="Captured patient last name.")
    date_of_birth: str | None = Field(default=None, description="Captured patient date of birth in YYYY-MM-DD format.")
    phone_number: str | None = Field(default=None, description="Captured patient phone number if provided.")
    medical_concern: str | None = Field(
        default=None,
        description="Concise summary of the patient's stated medical question or concern.",
    )
    last_tool_status: str | None = Field(
        default=None,
        description="Latest status returned by the authenticate_patient tool (success, multiple_matches, invalid_request, not_found).",
    )


AUTHENTICATION_INSTRUCTIONS = """
You verify the patient for Dr. Indigo, collect their current medical concern, and hand things off once you have both.
Keep the conversation relaxed and first-person so it sounds like one assistant continuing the chat.

Follow this process:
1. Acknowledge what the patient just shared, then segue directly into gathering the legal first name, last name, and
    date of birth (YYYY-MM-DD). No need to announce your role; just keep things warm and conversational.
2. Confirm spelling when uncertain. Once you have those three fields, call the authenticate_patient tool. Do not include
    a phone number on the first attempt. The tool responds with a status and may provide an MRN.
3. If the tool reports `multiple_matches`, let the patient know there are several people with that name and birth date
    and ask for a phone number (with area code). Set `requires_phone_number` to true and include `phone_number` in
    `missing_fields` until it is provided. Only call the tool again after you receive the phone number.
4. If the tool returns `invalid_request`, gently explain what needs to be corrected (for example, date format or phone
    length), keep `is_authenticated` false, and ask the patient to try again.
5. When the tool succeeds, set `is_authenticated` to true, save the MRN, and reassure the patient their chart is open.
    Do not read the MRN back; a simple acknowledgment is enough.
6. After authentication, gather a concise summary of the patient's medical question or concern if you do not already have
    one. Summarize the concern in the `medical_concern` field.
7. Set `triage_ready` to true only when `is_authenticated` is true AND `medical_concern` is populated. Keep
    `missing_fields` updated with any remaining information you still require.
8. Populate `message_to_patient` every turn with the exact statement you want the patient to see.

Response requirements:
- Always return JSON that matches the PatientAuthenticationResult schema.
- Keep the tone friendly, supportive, and succinct—like a single assistant staying with the patient.
- Never fabricate MRN values. Only use the MRN provided by the tool.
- Ask for a phone number only when the tool tells you there are multiple matches.
"""


def create_executor_agent(client: AzureOpenAIChatClient) -> AgentExecutor:
    agent = AgentExecutor(
        client.create_agent(
            instructions=AUTHENTICATION_INSTRUCTIONS,
            tools=[authenticate_patient],
            response_format=PatientAuthenticationResult,
            name="PatientAuthenticationAgent",
        ),
        output_response=False,
        id="patient_authentication_agent_executor",
    )
    return agent


def create_agent(client: AzureOpenAIChatClient) -> ChatAgent:
    agent = ChatAgent(
        chat_client=client,
        instructions=AUTHENTICATION_INSTRUCTIONS,
        tools=[authenticate_patient],
        name="PatientAuthenticationAgent",
        response_format=PatientAuthenticationResult,
    )
    return agent