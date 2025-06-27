import streamlit as st
import base64
import pandas as pd
import json
from processor import ContractExtractor, SoftwareContract

# Set the page title and configure the layout
st.set_page_config(
    page_title="Software Contract Data Extractor",
    layout="wide"
)

# Display the application title
st.title("Software Contract Data Extractor")


def display_pdf(file):
    """Display a PDF using Mozilla's PDF.js viewer."""
    pdf_bytes = file.getvalue()

    st.download_button(
        label="📥 Download PDF",
        data=pdf_bytes,
        file_name="contract.pdf",
        mime="application/pdf"
    )

    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

    pdf_js_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PDF Viewer</title>
        <style>
            #pdf-container {{
                width: 100%;
                height: 750px;
                overflow: auto;
                background: #fafafa;
                border: 1px solid #e0e0e0;
            }}
            .pdf-page-canvas {{
                display: block;
                margin: 5px auto;
                border: 1px solid #e0e0e0;
            }}
        </style>
    </head>
    <body>
        <div id="pdf-container"></div>
        <script type="module">
            import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/5.0.375/pdf.min.mjs';
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/5.0.375/pdf.worker.min.mjs';

            const pdfData = atob('{base64_pdf}');
            const pdfBytes = new Uint8Array(pdfData.length);
            for (let i = 0; i < pdfData.length; i++) {{
                pdfBytes[i] = pdfData.charCodeAt(i);
            }}

            const loadingTask = pdfjsLib.getDocument({{ data: pdfBytes }});
            loadingTask.promise.then(function(pdf) {{
                const container = document.getElementById('pdf-container');

                for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {{
                    pdf.getPage(pageNum).then(function(page) {{
                        const scale = 1.5;
                        const viewport = page.getViewport({{scale: scale}});

                        const canvas = document.createElement('canvas');
                        canvas.className = 'pdf-page-canvas';
                        canvas.width = viewport.width;
                        canvas.height = viewport.height;
                        container.appendChild(canvas);

                        const context = canvas.getContext('2d');
                        const renderContext = {{
                            canvasContext: context,
                            viewport: viewport
                        }};
                        page.render(renderContext);
                    }});
                }}
            }}).catch(function(error) {{
                document.getElementById('pdf-container').innerHTML = 
                    '<div style="color: red; padding: 20px;">Error loading PDF. Please try downloading instead.</div>';
            }});
        </script>
    </body>
    </html>
    """

    st.components.v1.html(pdf_js_html, height=800)


def display_contract_data(contract_data: SoftwareContract):
    """Display the extracted contract data in a table format"""
    with st.container():
        st.subheader("Extracted Contract Information")

        # Create a dictionary with proper field mappings
        data_dict = {
            "Software/System Name": contract_data.software_system_name or "NULL",
            "Vendor Name (DOING BUSINESS AS)": contract_data.vendor_name_dba or "NULL",
            "Vendor Name (LEGAL ENTITY)": contract_data.vendor_name_legal or "NULL",
            "Contract Start": contract_data.contract_start if contract_data.contract_start else "NULL",
            "Contract End": contract_data.contract_end if contract_data.contract_end else "NULL",
            "Contract Period": f"{contract_data.contract_period} months" if contract_data.contract_period is not None else "NULL",
            "Auto-renewal": "TRUE" if contract_data.auto_renewal is True else "FALSE" if contract_data.auto_renewal is False else "NULL",
            "Cancellation Notice (INITIAL TERM, DAYS)": str(
                contract_data.cancellation_notice_initial) if contract_data.cancellation_notice_initial is not None else "NULL",
            "Cancellation Notice (ONGOING, DAYS)": str(
                contract_data.cancellation_notice_ongoing) if contract_data.cancellation_notice_ongoing is not None else "NULL",
            "Payment Terms": contract_data.payment_terms if contract_data.payment_terms else "NULL",
            "Payment Delay": contract_data.payment_delay if contract_data.payment_delay else "NULL",
            "Payment amount, setup fee": f"${contract_data.payment_amount_setup:.2f}" if contract_data.payment_amount_setup is not None else "NULL",
            "Payment amount per terms": f"${contract_data.payment_amount_per_terms:.2f}" if contract_data.payment_amount_per_terms is not None else "NULL",
            "SLA/Uptime Guarantee": contract_data.sla_uptime_guarantee if contract_data.sla_uptime_guarantee else "NULL",
            "Integration Clauses": contract_data.integration_clauses if contract_data.integration_clauses else "NULL",
            "Data Ownership": contract_data.data_ownership or "DEALER",
            "License Count": str(contract_data.license_count) if contract_data.license_count != -1 else "Unlimited",
        }

        # Display as a table with proper alignment
        st.markdown("### Contract Details")

        # Use a table for better alignment
        df = pd.DataFrame(list(data_dict.items()), columns=['Field', 'Value'])

        # Display as HTML table with custom styling
        st.markdown(
            df.to_html(index=False, escape=False, classes='contract-table'),
            unsafe_allow_html=True
        )

        # Add export functionality
        st.markdown("### Export Options")
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name="contract_data.csv",
                mime="text/csv"
            )
        with col2:
            json_data = json.dumps(data_dict, indent=2)
            st.download_button(
                label="📥 Download as JSON",
                data=json_data,
                file_name="contract_data.json",
                mime="application/json"
            )

        # Add custom CSS for better table styling
        st.markdown("""
        <style>
        .contract-table {
            width: 100%;
            border-collapse: collapse;
        }
        .contract-table th {
            background-color: #f0f2f6;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #ddd;
        }
        .contract-table td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        .contract-table tr:hover {
            background-color: #f5f5f5;
        }
        </style>
        """, unsafe_allow_html=True)


# Create a file uploader for PDF files
uploaded_file = st.file_uploader("Upload or drag and drop a PDF contract file", type=["pdf"])

# Process the uploaded PDF file
if uploaded_file is not None:
    # Initialize the ContractExtractor with Gemini API key from Streamlit secrets
    api_key = st.secrets["config"]["gemini_api_key"]

    # Get few_shot_examples_path if it exists, otherwise None
    few_shot_examples_path = None
    if "config" in st.secrets and "few_shot_examples_path" in st.secrets["config"]:
        few_shot_examples_path = st.secrets["config"]["few_shot_examples_path"]

    extractor = ContractExtractor(api_key=api_key, few_shot_examples_path=few_shot_examples_path)

    # Display a spinner while processing
    with st.spinner("Extracting contract data from PDF..."):
        try:
            # Extract contract data from the uploaded PDF
            contract_data = extractor.extract_data_from_uploaded_file(uploaded_file)

            # Create two columns for side-by-side display
            col1, col2 = st.columns(2)

            # Display PDF in the left column
            with col1:
                st.subheader("PDF Document")
                display_pdf(uploaded_file)

            # Display extracted fields in the right column
            with col2:
                display_contract_data(contract_data)

        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            st.error("Please check the logs for more details.")
            import traceback

            st.code(traceback.format_exc())
else:
    # Display instructions when no file is uploaded
    st.info("Please upload a PDF contract file to extract contract information.")

    # Show empty placeholder for the layout
    col1, col2 = st.columns(2)
    with col1:
        st.empty()
    with col2:
        st.empty()