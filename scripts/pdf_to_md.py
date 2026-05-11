import os
import fitz  # PyMuPDF

def pdf_to_markdown(root_folder, output_file):
    with open(output_file, 'w', encoding='utf-8') as md_file:
        # Header
        md_file.write("# 📚 SUD TIZIMI YAGONA BILIMLAR BAZASI\n\n")
        md_file.write("> Ushbu hujjat avtomatik tarzda barcha yo'riqnomalardan yig'ildi.\n\n")
        
        pdf_count = 0
        
        # Recursive walk
        for root, dirs, files in os.walk(root_folder):
            for filename in files:
                if filename.lower().endswith('.pdf'):
                    pdf_path = os.path.join(root, filename)
                    try:
                        doc = fitz.open(pdf_path)
                        title = filename.replace('.pdf', '').replace('_', ' ').upper()
                        
                        # Section Header
                        md_file.write(f"\n---\n## 📖 {title}\n")
                        md_file.write(f"*(Manba: {filename})*\n\n")
                        
                        text = ""
                        for page in doc:
                            text += page.get_text()
                        
                        # Clean text
                        clean_text = text.replace('  ', ' ').replace('\n', ' \n')
                        md_file.write(clean_text + "\n")
                        
                        print(f"✅ {filename} qo'shildi ({len(doc)} bet)...")
                        pdf_count += 1
                        doc.close()
                    except Exception as e:
                        print(f"❌ Xatolik: {filename} - {e}")

    if pdf_count > 0:
        print(f"\n🎉 Tayyor! {pdf_count} ta fayl '{output_file}' ga joylandi.")
    else:
        print(f"\n⚠️ '{root_folder}' ichidan hech qanday PDF topilmadi.")

# Execution
if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs('data', exist_ok=True)
    pdf_to_markdown('data', 'data/knowledge.md')
