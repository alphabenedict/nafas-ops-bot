import logging
from openai import OpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


SYSTEM_PROMPT = """\
Kamu adalah NafasOps Bot — asisten operasional internal Nafas yang ramah dan cerdas.
Nafas adalah perusahaan yang fokus pada kualitas udara. Kamu bertindak seperti teman kerja \
yang sedang sharing update ke tim, bukan robot yang melapor.

Panduan gaya bicara:
- Gunakan bahasa Indonesia yang santai tapi tetap profesional.
- Mulai dengan sapaan ringan atau komentar singkat tentang datanya (misal: "Bulan ini lumayan sibuk nih!" atau "Semua lancar sejauh ini 👍").
- Sampaikan angka-angka penting tapi jangan cuma daftar — kasih konteks atau insight singkat.
- Gunakan emoji secukupnya biar lebih hidup, tapi jangan berlebihan.
- Akhiri dengan komentar penutup yang supportive atau actionable kalau relevan.
- Tetap ringkas, maksimal 2-3 paragraf pendek.
- JANGAN mengarang data. Hanya gunakan data yang diberikan.
"""


def humanize_summary(raw_summary: str) -> str:
    """Transform a structured summary into a natural, conversational message."""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Berikut data ringkasan operasional. Tolong sampaikan ulang dengan gaya "
                        "santai dan natural, seperti kamu lagi sharing update ke tim:\n\n"
                        f"{raw_summary}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=600,
        )
        result = response.choices[0].message.content.strip()
        logger.info("AI summary generated successfully")
        return result
    except Exception as e:
        logger.warning("AI summarization failed, falling back to raw: %s", e)
        return raw_summary


def humanize_client_info(client_name: str, raw_info: str) -> str:
    """Transform structured client info into a friendly conversational response."""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Berikut data klien '{client_name}'. Tolong sampaikan ulang dengan gaya "
                        "natural, seperti kamu lagi briefing ke teknisi tentang klien ini:\n\n"
                        f"{raw_info}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=400,
        )
        result = response.choices[0].message.content.strip()
        logger.info("AI client info generated successfully")
        return result
    except Exception as e:
        logger.warning("AI client info failed, falling back to raw: %s", e)
        return raw_info
