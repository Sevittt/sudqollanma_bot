import PyPDF2

def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page_num in range(len(reader.pages)):
            text += f"--- PAGE {page_num + 1} ---\n"
            text += reader.pages[page_num].extract_text()
        return text

pdf_text = extract_text_from_pdf('Ишларни судьялар ўртасида автоматик тарзда тақсимлаш ва қайта тақсимлаш ҳамда бирлаштириш тартиби.pdf')
print(pdf_text)