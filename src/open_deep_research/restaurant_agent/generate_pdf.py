import base64
import io
import json
import os
import tempfile
from typing import List

import markdown2
from PIL import Image as PILImage
from PyPDF2 import PdfMerger
from weasyprint import HTML

from restaurant_researcher import MenuWithImages


def markdown_to_pdf(markdown_text: str, title: str) -> bytes:
    """
    Convert markdown text to PDF using WeasyPrint.
    
    Args:
        markdown_text: Markdown string to convert
        title: Title for the PDF page
    
    Returns:
        PDF bytes
    """
    # Convert markdown to HTML with HTML support enabled
    html_content = markdown2.markdown(markdown_text, extras=['html'])
    
    # Create styled HTML document
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                line-height: 1.6;
                margin: 40px;
                color: #333;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #2c3e50;
                margin-top: 30px;
                margin-bottom: 15px;
                page-break-after: avoid;
            }}
            h1 {{ font-size: 28px; }}
            h2 {{ font-size: 24px; }}
            h3 {{ font-size: 20px; }}
            p {{
                margin-bottom: 15px;
                text-align: justify;
            }}
            ul, ol {{
                margin-bottom: 15px;
                padding-left: 30px;
            }}
            li {{
                margin-bottom: 8px;
            }}
            strong, b {{
                font-weight: bold;
                color: #2c3e50;
            }}
            em, i {{
                font-style: italic;
            }}
            code {{
                background-color: #f8f9fa;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                margin-bottom: 20px;
            }}
            blockquote {{
                border-left: 4px solid #3498db;
                margin: 20px 0;
                padding-left: 20px;
                color: #555;
                font-style: italic;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            /* Menu item styling */
            .menu-item {{
                page-break-inside: avoid;
                margin-bottom: 30px;
            }}
            /* Image styling for menu items */
            img {{
                max-width: 200px;
                height: auto;
                border-radius: 8px;
                margin: 10px 0;
                display: block;
            }}
            /* Ensure menu items don't break across pages */
            h2 + p + div {{
                page-break-inside: avoid;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Generate PDF using WeasyPrint
    html_doc = HTML(string=styled_html)
    pdf_bytes = html_doc.write_pdf()
    
    return pdf_bytes


def menu_to_markdown(menu: MenuWithImages) -> str:
    """
    Convert menu to markdown format with inline images.
    
    Args:
        menu: MenuWithImages object
    
    Returns:
        Markdown string
    """
    markdown_lines = ["# Restaurant Menu\n"]
    
    for item in menu.items:
        markdown_lines.append(f'<div class="menu-item">\n')
        markdown_lines.append(f'<h2>{item.name} - ${item.price:.2f}</h2>\n')
        markdown_lines.append(f'<p>{item.recipe}</p>\n')
        
        if hasattr(item, 'image') and item.image:
            # Add image inline with the menu item, sized smaller
            markdown_lines.append(f'<img src="data:image/png;base64,{item.image}" alt="{item.name}">\n')
        
        markdown_lines.append(f'</div>\n')
        markdown_lines.append("<hr>\n")
    
    return "\n".join(markdown_lines)


def image_to_pdf(image: str, title: str) -> bytes:
    """
    Convert an image to a single-page PDF.
    
    Args:
        image: Image object with b64_json attribute
        title: Title for the PDF page
    
    Returns:
        PDF bytes
    """
    # Convert image data to PIL Image
    image_data = base64.b64decode(image)
    pil_image = PILImage.open(io.BytesIO(image_data))
    
    # Save image to temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        pil_image.save(temp_file.name, 'PNG')
        temp_file_path = temp_file.name
    
    try:
        # Create HTML with the image
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    margin: 40px;
                    text-align: center;
                }}
                h1 {{
                    color: #2c3e50;
                    margin-bottom: 30px;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <img src="file://{temp_file_path}" alt="{title}">
        </body>
        </html>
        """
        
        # Generate PDF using WeasyPrint
        html_doc = HTML(string=html_content)
        pdf_bytes = html_doc.write_pdf()
        
        return pdf_bytes
    
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)


def combine_pdfs(pdf_list: List[bytes]) -> bytes:
    """
    Combine multiple PDF bytes into one PDF.
    
    Args:
        pdf_list: List of PDF bytes
    
    Returns:
        Combined PDF bytes
    """
    
    merger = PdfMerger()
    
    # Save each PDF to temporary file and merge
    temp_files = []
    try:
        for i, pdf_bytes in enumerate(pdf_list):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_bytes)
                temp_file_path = temp_file.name
                temp_files.append(temp_file_path)
                merger.append(temp_file_path)
        
        # Write combined PDF to bytes
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_file:
            merger.write(output_file.name)
            merger.close()
            
            with open(output_file.name, 'rb') as f:
                combined_pdf = f.read()
            
            # Clean up output file
            os.unlink(output_file.name)
            
            return combined_pdf
    
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass


def generate_pdf(report: str, storefront_rendering: str, menu: MenuWithImages) -> bytes:
    """
    Generate a multi-page PDF with report, menu (with inline images), and storefront image.
    
    Args:
        report: Markdown string for the report
        storefront_rendering: Image object for storefront
        menu: MenuWithImages object
    
    Returns:
        PDF bytes
    """
    pdf_list = []
    
    # 1. Generate report PDF
    print("Generating report PDF...")
    report_pdf = markdown_to_pdf(report, "Restaurant Report")
    pdf_list.append(report_pdf)
    
    # 2. Generate menu PDF (with inline images)
    print("Generating menu PDF with inline images...")
    menu_markdown = menu_to_markdown(menu)
    menu_pdf = markdown_to_pdf(menu_markdown, "Restaurant Menu")
    pdf_list.append(menu_pdf)
    
    # 3. Generate storefront image PDF
    print("Generating storefront PDF...")
    storefront_pdf = image_to_pdf(storefront_rendering, "Storefront Rendering")
    pdf_list.append(storefront_pdf)
    
    # 4. Combine all PDFs
    print("Combining PDFs...")
    combined_pdf = combine_pdfs(pdf_list)
    
    return combined_pdf


def save_pdf_to_file(report: str, storefront_rendering: str, menu: MenuWithImages, filename: str = "restaurant_report.pdf"):
    """
    Generate PDF and save to file.
    
    Args:
        report: Markdown string for the report
        storefront_rendering: Image object for storefront
        menu: MenuWithImages object
        filename: Output filename
    """
    pdf_bytes = generate_pdf(report, storefront_rendering, menu)
    
    with open(filename, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"PDF saved as {filename}")


# Example usage
if __name__ == "__main__":
    # Load sample data
    with open("report.md", "r") as f:
        report = f.read()
    
    with open("storefront.txt", "r") as f:
        storefront_rendering = f.read()

    with open("menu2.json", "r") as f:
        menu_data = json.load(f)
        menu = MenuWithImages(**menu_data)
    
    # Generate and save PDF
    save_pdf_to_file(report, storefront_rendering, menu)