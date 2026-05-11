"""
generate_certificate.py — Sertifikat PDF generatsiyasi
=======================================================
Ishlatish:
    python generate_certificate.py --user_id <uid> --course_id <cid>

Logika:
  1. Firestore'dan foydalanuvchi, kurs va progress ma'lumotlarini oladi
  2. Gemini 2.0 Flash Lite orqali shaxsiylashtirilgan matn yaratadi
  3. ReportLab orqali A4 PDF sertifikat chizadi
  4. PDF ni Firebase Storage ga yuklaydi
  5. Firestore'dagi progress va certificates kolleksiyasini yangilaydi
"""

import argparse
import datetime
import io
import logging
import os

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Firebase & Gemini init ───────────────────────────────────────────────────

from loader import get_db
import firebase_admin
from firebase_admin import storage
from google import genai
from google.genai import types as genai_types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "educationapp-4780a.appspot.com")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
db = get_db()


# ─── PDF generatsiya ──────────────────────────────────────────────────────────

def _build_pdf(
    full_name: str,
    course_title: str,
    certificate_title: str,
    completion_date: datetime.datetime,
    xp_earned: int,
    gemini_text: str,
) -> bytes:
    """ReportLab orqali A4 sertifikat PDF yaratadi va bytes qaytaradi."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = A4  # 595 x 842 pt

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    # ── Fon ──────────────────────────────────────────────────────────────────
    c.setFillColorRGB(0.98, 0.97, 0.95)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Yuqori chegara chizig'i ───────────────────────────────────────────────
    gold = colors.HexColor("#C8A84B")
    navy = colors.HexColor("#1A2B5A")

    c.setStrokeColor(gold)
    c.setLineWidth(6)
    c.line(30, H - 30, W - 30, H - 30)
    c.line(30, 30, W - 30, 30)
    c.setLineWidth(1.5)
    c.line(36, H - 36, W - 36, H - 36)
    c.line(36, 36, W - 36, 36)

    # Burchak bezaklari
    for x, y in [(30, H - 30), (W - 30, H - 30), (30, 30), (W - 30, 30)]:
        c.setFillColor(gold)
        c.circle(x, y, 5, fill=1, stroke=0)

    # ── Sarlavha: SERTIFIKAT ──────────────────────────────────────────────────
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(W / 2, H - 100, "SERTIFIKAT")

    c.setStrokeColor(gold)
    c.setLineWidth(2)
    c.line(W / 2 - 80, H - 108, W / 2 + 80, H - 108)

    # ── "Ushbu sertifikat beriladi" ────────────────────────────────────────────
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(W / 2, H - 145, "Ushbu sertifikat")

    # ── Ism ───────────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(navy)
    c.drawCentredString(W / 2, H - 195, full_name.upper())

    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(W / 2 - 160, H - 202, W / 2 + 160, H - 202)

    # ── "ga beriladi, chunki u ..." ────────────────────────────────────────────
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(W / 2, H - 228, "ga beriladi, chunki u")

    # ── Kurs nomi ─────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(navy)
    _draw_wrapped(c, f'"{certificate_title}"', W / 2, H - 265, W - 120, 20)

    # ── "kursini muvaffaqiyatli tamomladi" ────────────────────────────────────
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(W / 2, H - 310, "kursini muvaffaqiyatli tamomladi.")

    # ── Gemini matni (shaxsiylashtirilgan) ─────────────────────────────────────
    c.setFont("Helvetica-Oblique", 11)
    c.setFillColor(colors.HexColor("#555555"))
    _draw_wrapped(c, gemini_text, W / 2, H - 355, W - 140, 16, centered=True)

    # ── Statistika paneli ─────────────────────────────────────────────────────
    panel_y = H - 460
    c.setFillColorRGB(0.95, 0.93, 0.88)
    c.roundRect(60, panel_y - 20, W - 120, 60, 10, fill=1, stroke=0)

    date_str = completion_date.strftime("%d.%m.%Y")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(navy)
    c.drawCentredString(W * 0.25, panel_y + 22, "Tugallangan sana")
    c.drawCentredString(W * 0.5,  panel_y + 22, "Qozonilgan XP")
    c.drawCentredString(W * 0.75, panel_y + 22, "Daraja")

    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(W * 0.25, panel_y + 5,  date_str)
    c.drawCentredString(W * 0.5,  panel_y + 5,  f"{xp_earned} XP")
    c.drawCentredString(W * 0.75, panel_y + 5,  "Malakali")

    # ── Imzo chizig'i ─────────────────────────────────────────────────────────
    sig_y = panel_y - 80
    c.setStrokeColor(navy)
    c.setLineWidth(1)
    c.line(W / 2 - 90, sig_y, W / 2 + 90, sig_y)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(W / 2, sig_y - 14, "BMI Academy raxbariyati")

    # ── Pastki marka ──────────────────────────────────────────────────────────
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#999999"))
    c.drawCentredString(W / 2, 50, "Bu sertifikat BMI Academy tomonidan berilgan va elektron tarzda tasdiqlangan.")

    c.save()
    return buf.getvalue()


def _draw_wrapped(c, text: str, cx: float, y: float, max_w: float,
                  line_h: float, centered: bool = True):
    """Uzun matnni so'zlarga bo'lib chizadi."""
    from reportlab.pdfgen import canvas as _  # noqa – faqat import uchun
    words = text.split()
    line = ""
    lines = []
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, c._fontname, c._fontsize) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)

    for i, ln in enumerate(lines):
        ly = y - i * line_h
        if centered:
            c.drawCentredString(cx, ly, ln)
        else:
            c.drawString(cx - max_w / 2, ly, ln)


# ─── Gemini matn generatsiyasi ────────────────────────────────────────────────

def _generate_gemini_text(full_name: str, course_title: str, xp: int) -> str:
    prompt = (
        f"O'zbek tilida, rasmiy va iliqroq uslubda, 2 ta qisqa jumla yoz. "
        f"Bu sertifikat egasi {full_name} uchun '{course_title}' kursini "
        f"tugatgani uchun tabrik matni. {xp} XP qozondi. "
        f"Faqat matnni yoz, tirnoq yoki boshqa belgilar qo'shma."
    )
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=120,
            ),
        )
        return response.text.strip()
    except Exception as e:
        log.warning(f"Gemini xatosi: {e}. Default matn ishlatiladi.")
        return (
            f"{full_name}, siz '{course_title}' kursini muvaffaqiyatli tamomlladingiz. "
            "Bu sizning kasbiy rivojlanishingizga muhim hissa qo'shadi."
        )


# ─── Firebase Storage yuklash ─────────────────────────────────────────────────

def _upload_to_storage(pdf_bytes: bytes, user_id: str, course_id: str) -> str:
    bucket = storage.bucket(STORAGE_BUCKET)
    blob_path = f"certificates/{user_id}_{course_id}.pdf"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    blob.make_public()
    log.info(f"PDF yuklandi: {blob.public_url}")
    return blob.public_url


# ─── Asosiy funksiya ──────────────────────────────────────────────────────────

def generate_certificate(user_id: str, course_id: str) -> str | None:
    """
    Sertifikat yaratadi va PDF URL qaytaradi.
    Barcha Firestore yangilanishlarini ham bajaradi.
    """
    # 1. Ma'lumotlarni olish
    user_doc = db.collection("users").document(user_id).get()
    course_doc_ref = db.collection("courses").document(course_id).get()
    progress_id = f"{user_id}_{course_id}"
    progress_doc = db.collection("user_course_progress").document(progress_id).get()

    if not user_doc.exists or not course_doc_ref.exists or not progress_doc.exists:
        log.error("Foydalanuvchi, kurs yoki progress topilmadi.")
        return None

    user     = user_doc.to_dict()
    course   = course_doc_ref.to_dict()
    progress = progress_doc.to_dict()

    full_name        = user.get("fullName") or user.get("firstName", "Noma'lum")
    course_title     = course.get("title", "")
    cert_title       = course.get("certificateTitle") or course_title
    xp_earned        = progress.get("earnedXp", 0)
    completed_at     = progress.get("completedAt")
    if completed_at is None:
        completed_at = datetime.datetime.now(tz=datetime.timezone.utc)
    elif hasattr(completed_at, "timestamp"):
        completed_at = completed_at.ToDatetime(tzinfo=datetime.timezone.utc)

    # 2. Gemini matn
    log.info("Gemini matn yaratilmoqda...")
    gemini_text = _generate_gemini_text(full_name, course_title, xp_earned)

    # 3. PDF yaratish
    log.info("PDF yaratilmoqda...")
    pdf_bytes = _build_pdf(
        full_name=full_name,
        course_title=course_title,
        certificate_title=cert_title,
        completion_date=completed_at,
        xp_earned=xp_earned,
        gemini_text=gemini_text,
    )

    # 4. Storage ga yuklash
    log.info("Firebase Storage ga yuklanmoqda...")
    pdf_url = _upload_to_storage(pdf_bytes, user_id, course_id)

    # 5. certificates kolleksiyasiga yozish
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    db.collection("certificates").document(progress_id).set({
        "userId": user_id,
        "courseId": course_id,
        "courseTitle": course_title,
        "userName": full_name,
        "pdfUrl": pdf_url,
        "geminiSummary": gemini_text,
        "issuedAt": now,
    })

    # 6. Progress ga certificateUrl qo'shish
    db.collection("user_course_progress").document(progress_id).update({
        "certificateUrl": pdf_url,
        "certificateIssuedAt": now,
    })

    log.info(f"✅ Sertifikat yaratildi: {pdf_url}")
    return pdf_url


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sertifikat PDF generatsiyasi")
    parser.add_argument("--user_id",   required=True, help="Firebase Auth UID")
    parser.add_argument("--course_id", required=True, help="Firestore courses doc ID")
    args = parser.parse_args()

    url = generate_certificate(args.user_id, args.course_id)
    if url:
        print(f"\n✅ Sertifikat tayyor: {url}")
    else:
        print("\n❌ Sertifikat yaratishda xatolik yuz berdi.")
