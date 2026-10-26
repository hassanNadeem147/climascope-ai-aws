import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path
import boto3
from pypdf import PdfReader, apply_configuration
from langchain_core.documents import Document
from app.core.config import get_settings
# Create a logger for this file
logger = logging.getLogger(__name__)
# Load application settings once
settings = get_settings()
# Create the S3 client once and reuse it
s3 = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value(),
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
)
def load_docs() -> Iterator[Document]:
    """Download PDFs from S3 and yield one document per page."""
    # Get a tool to list S3 files in batches
    paginator = s3.get_paginator("list_objects_v2")
    # Keep track of processed PDFs and pages
    pdf_count = 0
    successful_pdfs = 0
    failed_pdfs = 0
    page_count = 0
    # Create a temporary folder for downloaded PDFs
    with tempfile.TemporaryDirectory() as temp_dir:
        # Get each batch of files from S3
        for response in paginator.paginate(
            Bucket=settings.BUCKET_NAME
        ):
            # Go through each file in this batch
            for obj in response.get("Contents", []):
                # Get the file name and path from S3
                key = obj["Key"]
                # Skip files that are not PDFs
                if not key.lower().endswith(".pdf"):
                    continue
                pdf_count += 1
                # Create a temporary path for this PDF
                pdf_path = Path(temp_dir) / f"{pdf_count}.pdf"
                try:
                    # Download the PDF from S3
                    s3.download_file(
                        settings.BUCKET_NAME,
                        key,
                        str(pdf_path),
                    )
                    # Allow more work for complex PDF content
                    with apply_configuration(
                        stream_parsing_work_maximum_count=10_000_000
                    ):
                        # Open the downloaded PDF
                        with pdf_path.open("rb") as pdf_file:
                            reader = PdfReader(pdf_file)
                            # Read each page separately
                            for page_index, page in enumerate(reader.pages):
                                # Extract text from the current page
                                text = page.extract_text() or ""
                                page_count += 1
                                # Create a Document for this page
                                yield Document(
                                    page_content=text,
                                    metadata={
                                        # Save the original S3 file location
                                        "source": (
                                            f"s3://{settings.BUCKET_NAME}/{key}"
                                        ),
                                        # Save the page index; the first page is 0
                                        "page": page_index,
                                    },
                                )
                    successful_pdfs += 1
                except Exception:
                    # Count and log PDFs that fail
                    failed_pdfs += 1
                    logger.exception(
                        "Failed to process PDF: %s",
                        key,
                    )
                finally:
                    # Delete the temporary PDF after processing
                    pdf_path.unlink(missing_ok=True)
    # Print the final loading summary in the logs
    logger.info(
        "PDF loading finished: found=%d, succeeded=%d, failed=%d, pages=%d",
        pdf_count,
        successful_pdfs,
        failed_pdfs,
        page_count,
    )