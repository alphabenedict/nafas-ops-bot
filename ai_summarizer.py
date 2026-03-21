import logging
import json
from datetime import datetime
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

CHAT_SYSTEM_PROMPT = """\
Kamu adalah NafasOps Bot — asisten operasional internal Nafas yang ramah dan cerdas.
Nafas adalah perusahaan yang fokus pada kualitas udara dan menyediakan layanan perawatan \
perangkat pemurni udara untuk berbagai klien.

Kamu bisa menjawab pertanyaan seputar:
- Ringkasan operasional (bulanan / tahunan)
- Info klien (alamat, device, riwayat service, teknisi)
- Data layanan (on time vs late, jenis service, dll.)
- Pertanyaan umum tentang operasional Nafas

Panduan gaya bicara:
- Gunakan bahasa Indonesia yang santai tapi tetap profesional.
- Jawab pertanyaan secara langsung dan natural, seperti teman kerja yang ditanya.
- Berikan insight langsung dari data yang kamu terima. JANGAN PERNAH menyuruh user untuk mengetik perintah /summary, /ask, atau perintah apapun. Kamu BISA menjawabnya langsung karena data sudah diberikan.
- Gunakan emoji secukupnya biar lebih hidup.
- Tetap ringkas dan to-the-point.
- JANGAN mengarang data. Kalau tidak ada datanya, bilang jujur.
- Kalau user menyapa atau chat ringan, balas dengan ramah dan tawarkan bantuan.

Hari ini tanggal: {today}
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


def chat_with_data(user_message: str, data_context: str) -> str:
    """Handle a free-text user message with operational data as context.
    
    Args:
        user_message: The user's natural language message.
        data_context: Pre-built string of available data (summaries, client list, etc.)
    
    Returns:
        A natural language response.
    """
    today = datetime.now().strftime("%d %B %Y")
    system = CHAT_SYSTEM_PROMPT.format(today=today)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        "Berikut data operasional yang tersedia saat ini:\n\n"
                        f"{data_context}\n\n"
                        "---\n\n"
                        f"Pertanyaan/pesan dari user: {user_message}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=800,
        )
        result = response.choices[0].message.content.strip()
        logger.info("AI chat response generated successfully")
        return result
    except Exception as e:
        logger.error("AI chat failed: %s", e)
        return (
            "Maaf, aku lagi ada kendala teknis nih 😅 "
            "Coba lagi nanti ya, atau pakai perintah /summary atau /ask."
        )

