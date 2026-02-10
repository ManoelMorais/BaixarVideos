import streamlit as st
import yt_dlp
import os
import re
from typing import Any, Dict, cast

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Universal Downloader", page_icon="📥")

if "link_input" not in st.session_state:
    st.session_state.link_input = ""

def clear_text():
    st.session_state.link_input = ""


st.title("📥 Baixador de Vídeos Multi-plataforma")
st.caption("Versão segura com isolamento de cookies e proteção de User-Agent.")


# --- LÓGICA DE COOKIES POR DOMÍNIO ---
def get_cookie_file(url: str) -> str | None:
    """Identifica o site e cria um arquivo temporário de cookies a partir das Secrets."""
    cookie_path = "temp_cookies.txt"
    cookie_content = None

    # 1. Identifica qual Secret usar
    if "youtube.com" in url or "youtu.be" in url:
        cookie_content = st.secrets.get("YOUTUBE_COOKIES")
    elif "instagram.com" in url:
        cookie_content = st.secrets.get("INSTAGRAM_COOKIES")

    # 2. Se houver conteúdo na Secret, cria o arquivo físico temporário
    if cookie_content and len(cookie_content.strip()) > 0:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(cookie_content.strip())
        return cookie_path

    # 3. Fallback para arquivo local (testes no seu PC)
    if os.path.exists("cookies.txt"):
        return "cookies.txt"

    return "cookies.txt" if os.path.exists("cookies.txt") else None


@st.cache_data(show_spinner=False)
def get_video_info(url: str, cookie_file: str | None) -> Dict[str, Any]:
    """Busca apenas o título e a thumb de forma instantânea."""
    ydl_opts: Dict[str, Any] = {
        "cookiefile": cookie_file,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        "extract_flat": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        return cast(Dict[str, Any], ydl.extract_info(url, download=False))


def clean_ansi(text: str) -> str:
    """Remove códigos de cores que sujam a barra de progresso."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def progress_hook(d: Dict[str, Any]):
    """Atualiza a barra de progresso com tratamento para downloads ultra-rápidos."""
    if d['status'] == 'downloading':
        # Remove cores ANSI e limpa a string
        p = clean_ansi(d.get('_percent_str', '0%'))
        try:
            # Converte ' 95.5%' para 0.955
            p_float = float(p.replace('%', '').strip()) / 100
            
            # Só atualiza a barra se houver mudança real ou se for o fim
            # Isso evita "atropelar" a interface do Streamlit
            progress_bar.progress(p_float, text=f"📥 Baixando... {p}")
        except:
            pass
    elif d['status'] == 'finished':
        # Força a barra para 100% quando terminar o download
        progress_bar.progress(1.0, text="✅ Download concluído! Convertendo...")


# --- INTERFACE PRINCIPAL ---
url = st.text_input("Cole o link aqui:", key="link_input", placeholder="https://...")

st.button("Limpar link", on_click=clear_text)

if url:
    # Seleciona o cookie correto antes de qualquer operação
    current_cookie_file = get_cookie_file(url)

    try:
        # 1. Extração de Informações (Preview)
        ydl_opts_info: Dict[str, Any] = {
            "cookiefile": current_cookie_file,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        }

        with yt_dlp.YoutubeDL(cast(Any, ydl_opts_info)) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                st.error("Não foi possível acessar o conteúdo.")
                st.stop()

            video_title = info.get("title", "Video_Sem_Nome")
            thumbnail = info.get("thumbnail")

            st.subheader(f"🎥 {video_title}")
            if isinstance(thumbnail, str):
                st.image(thumbnail, width=400)

        format_option = st.selectbox("Formato:", ["Vídeo (MP4)", "Áudio (MP3)"])

        if st.button("🚀 Iniciar Download"):
            progress_bar = st.progress(0, text="Preparando motor...")

            # 2. Configuração Final de Download
            ydl_opts_dl: Dict[str, Any] = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" if format_option == "Vídeo (MP4)" else 'bestaudio/best',
                "merge_output_format": "mp4",
                "outtmpl": "download_temp_%(id)s.%(ext)s",
                "progress_hooks": [progress_hook],
                "cookiefile": current_cookie_file,
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                "noplaylist": True,
                'nopart': True,  # Resolve o erro de "Unable to rename file"
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'logtostderr': False,
                'quiet': True,
                'no_warnings': True,
                "postprocessor_args": [
                    "-vcodec",
                    "libx264",  # Força o codec H.264 (universal)
                    "-acodec",
                    "aac",  # Força áudio AAC (padrão Apple)
                    "-pix_fmt",
                    "yuv420p",  # Garante compatibilidade com telas de retina
                ],
            }

            if format_option == "Áudio (MP3)":
                ydl_opts_dl["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]

            with yt_dlp.YoutubeDL(cast(Any, ydl_opts_dl)) as ydl:
                info_result = ydl.extract_info(url, download=True)
                if info_result:
                    actual_filename = ydl.prepare_filename(info_result)

                    if format_option == "Áudio (MP3)":
                        actual_filename = os.path.splitext(actual_filename)[0] + ".mp3"

                    # 3. Entrega do Arquivo
                    if os.path.exists(actual_filename):
                        with open(actual_filename, "rb") as file:
                            st.download_button(
                                label="💾 Salvar no Dispositivo",
                                data=file,
                                file_name=f"{video_title}.{'mp3' if format_option == 'Áudio (MP3)' else 'mp4'}",
                                mime=(
                                    "audio/mpeg"
                                    if format_option == "Áudio (MP3)"
                                    else "video/mp4"
                                ),
                            )
                        os.remove(actual_filename)  # Limpa o servidor

                        # Limpa o arquivo de cookies temporário por segurança
                        if current_cookie_file == "temp_cookies.txt":
                            os.remove(current_cookie_file)

    except Exception as e:
        st.error(
            f"Erro: O site bloqueou o acesso ou o link é inválido. Detalhe: {str(e)}"
        )
