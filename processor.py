from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from typing import List, Any, Optional
import os
import json
import logging
from pathlib import Path
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SoftwareContract(BaseModel):
    software_system_name: str = Field(description="Name of product or service")
    vendor_name_dba: str = Field(description="Company providing software or service (who is providing the servise?) (DOING BUSINESS AS)")
    vendor_name_legal: str = Field(description="Company providing software or service (who is providing the servise legal name?) (LEGAL ENTITY) ")
    contract_start: Optional[str] = Field(description="Contract start date (start = date of contract)", default=None)
    contract_end: Optional[str] = Field(description="Contract end date", default=None)
    contract_period: Optional[int] = Field(description="Contract duration (period of contract) in months", default=None)
    auto_renewal: Optional[bool] = Field(description="Is contract renewed (prolonged) automatically?", default=None)
    cancellation_notice_initial: Optional[int] = Field(
        description="Number of days required to cancel the contract (INITIAL TERM)", default=None)
    cancellation_notice_ongoing: Optional[int] = Field(
        description="Number of days required to cancel the contract (ONGOING)", default=None)
    payment_terms: Optional[str] = Field(description="Terms (monthly, yearly, user subscription, per licence, other)",
                                         default=None)
    payment_delay: Optional[int] = Field(description="Delay between invoice receiption and payment (in days)",
                                         default=None)
    payment_amount_setup: Optional[float] = Field(description="Payment amount, setup fee", default=None)
    payment_amount_per_terms: Optional[float] = Field(
        description="Payment amount per terms (per user, per month, per licence)", default=None)
    sla_uptime_guarantee: Optional[str] = Field(description="Any included SLA/Uptime guarantee terms", default=None)
    integration_clauses: Optional[str] = Field(description="Compatibility with DMS/CRM", default=None)
    data_ownership: str = Field(description="Who owns stored data, assume DEALER if not specified", default="DEALER")
    license_count: int = Field(
        description="Number of licenses, active users, seats. If not presented assume unlimited (mark as -1)",
        default=-1)


class ContractExtractor:
    """Service for extracting software contract information from PDFs."""

    def __init__(self, api_key: str, few_shot_examples_path: str = None):
        """
        Initialize contract extractor with Google API key.

        Args:
            api_key: Google Gemini API key
            few_shot_examples_path: Path to few-shot examples JSON file
        """
        self.client = genai.Client(api_key=api_key)
        self.few_shot_examples_path = few_shot_examples_path

        self.system_prompt = """
        You are an AI assistant specialized in extracting specific information from software contracts.
        Extract EXACTLY these fields from the contract. Pay close attention to the exact field names and data types.

        1. Software/System Name: The name of the product or service
        2. Vendor Name (DBA): Company name doing business as
        3. Vendor Name (Legal Entity): Legal entity name of the company
        4. Contract Start: Start date of the contract (format: YYYY-MM-DD)
        5. Contract End: End date of the contract (can be NULL if not specified)
        6. Contract Period: Duration in months (integer)
        7. Auto-renewal: Is the contract automatically renewed? (boolean: true/false)
        8. Cancellation Notice (Initial Term): Days required to cancel during initial term (integer)
        9. Cancellation Notice (Ongoing): Days required to cancel after initial term (integer)
        10. Payment Terms: Monthly, yearly, per user subscription, per license, or other
        11. Payment Amount Setup Fee: One-time setup fee amount (float)
        12. Payment Amount Per Terms: Recurring payment amount (float)
        13. SLA/Uptime Guarantee: Any service level agreement terms (can be NULL)
        14. Integration Clauses: Compatibility with DMS/CRM systems
        15. Data Ownership: Who owns the data (default to "DEALER" if not specified)
        16. License Count: Number of licenses/users/seats (use -1 for unlimited)

        IMPORTANT:
        - Use NULL for missing string values
        - Use null for missing date values
        - Use appropriate data types (string, integer, float, boolean)
        - For License Count, if unlimited or not specified, use -1
        - For Data Ownership, if not specified, default to "DEALER"
        - Extract dates in YYYY-MM-DD format
        - For payment amounts, extract numeric values only (no currency symbols)
        """

        self.main_prompt = "Please extract the contract information from the attached PDF document according to the specified fields."

    def create_few_shot_examples(self) -> List[Any]:
        """
        Create few-shot examples for the Gemini model.

        Returns:
            List of example prompts and responses
        """
        if not self.few_shot_examples_path or not os.path.exists(self.few_shot_examples_path):
            return []

        # Note: The original few-shot examples were for vehicle titles, not software contracts
        # If you have software contract examples, place them in the few_shot_examples_path
        # with the expected format matching the SoftwareContract model fields

        few_shot_examples = []
        try:
            with open(self.few_shot_examples_path, "r") as f:
                examples = json.load(f)

            for example in examples:
                # Skip if this is a vehicle title example (from original project)
                if "vehicle_vin" in example.get("expected_output", {}):
                    logger.info("Skipping vehicle title example - not applicable for software contracts")
                    continue

                filepath = Path(example["pdf_path"])
                if not filepath.exists():
                    logger.warning(f"Example PDF file not found: {example['pdf_path']}")
                    continue

                # Use the expected output directly if it matches our schema
                model_output = example.get("expected_output", {})

                few_shot_examples.extend(
                    [
                        "Please extract the contract information from the following PDF",
                        types.Part.from_bytes(
                            data=filepath.read_bytes(),
                            mime_type="application/pdf",
                        ),
                        json.dumps(model_output, indent=2),
                    ],
                )
        except Exception as e:
            logger.warning(f"Could not load few-shot examples: {str(e)}")

        return few_shot_examples

    def extract_data_from_pdf(self, pdf_data: bytes) -> SoftwareContract:
        """
        Extract contract data from PDF data.

        Args:
            pdf_data: PDF file data as bytes

        Returns:
            SoftwareContract object containing extracted contract information

        Raises:
            Exception: If extraction fails
        """
        try:
            few_shot_examples = self.create_few_shot_examples()

            response = self.client.models.generate_content(
                model="models/gemini-2.0-flash",
                contents=[
                    self.system_prompt,
                    *few_shot_examples,
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type="application/pdf",
                    ),
                    self.main_prompt,
                ],
                config={"response_mime_type": "application/json", "response_schema": SoftwareContract},
            )

            # Parse the JSON response
            result = response.parsed
            return result

        except Exception as e:
            logger.error(f"Error extracting contract data from PDF: {str(e)}")
            raise

    def extract_data_from_file(self, pdf_file_path: str) -> SoftwareContract:
        """
        Extract contract data from a PDF file.

        Args:
            pdf_file_path: Path to PDF file

        Returns:
            SoftwareContract object containing extracted contract information
        """
        with open(pdf_file_path, "rb") as f:
            pdf_data = f.read()

        return self.extract_data_from_pdf(pdf_data)

    def extract_data_from_uploaded_file(self, uploaded_file) -> SoftwareContract:
        """
        Extract contract data from a Streamlit uploaded file.

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            SoftwareContract object containing extracted contract information
        """
        # For Streamlit uploaded files, save to temp file first
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(uploaded_file.getvalue())
            temp_file_path = temp_file.name

        try:
            return self.extract_data_from_file(temp_file_path)
        finally:
            # Clean up the temp file
            os.unlink(temp_file_path)