import io
import os
import re
import json
import time
import uuid
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pypdf import PdfReader
from docx import Document
from mutagen.mp3 import MP3
import edge_tts

# ---------------------------------------------------------
# Configuração de Logs
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gerador-audio")

# ---------------------------------------------------------
# Diretório de Armazenamento Temporário
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Tempo limite para retenção de arquivos temporários (2 horas)
TEMPO_RETENCAO_SEGUNDOS = 2 * 3600

# ---------------------------------------------------------
# Inicialização do FastAPI
# ---------------------------------------------------------
app = FastAPI(
    title="API de Geração de Audiolivro e Sincronização de Texto",
    description="API assíncrona para extrair texto de PDF/DOCX, sintetizar áudio via Edge TTS e gerar mapa de tempo sincronizado por palavra.",
    version="1.0.0"
)

# Configuração de CORS para permitir requisições de qualquer front-end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Funções Auxiliares de Limpeza de Armazenamento
# ---------------------------------------------------------
def limpar_arquivos_antigos():
    """Remove pastas de jobs antigas para evitar estouro de disco."""
    agora = time.time()
    try:
        for job_folder in STORAGE_DIR.iterdir():
            if job_folder.is_dir():
                idade = agora - job_folder.stat().st_mtime
                if idade > TEMPO_RETENCAO_SEGUNDOS:
                    shutil.rmtree(job_folder, ignore_errors=True)
                    logger.info(f"Pasta temporária expirada removida: {job_folder.name}")
    except Exception as e:
        logger.error(f"Erro ao limpar arquivos antigos: {e}")

# ---------------------------------------------------------
# Extração e Limpeza de Textos
# ---------------------------------------------------------
def extrair_texto_pdf(conteudo_bytes: bytes, termo_cabecalho: Optional[str] = None) -> list[str]:
    """
    Lê o PDF e aplica filtros inteligentes:
    - Remove números de página soltos
    - Remove cabeçalhos repetitivos
    - Agrupa em frases e parágrafos fluidos
    """
    paragrafos_originais = []
    leitor = PdfReader(io.BytesIO(conteudo_bytes))
    termo_filtro = termo_cabecalho.strip().lower() if termo_cabecalho else None

    for pagina in leitor.pages:
        t = pagina.extract_text()
        if not t:
            continue

        linhas = t.split("\n")
        linhas_filtradas = []

        for linha in linhas:
            linha_limpa = linha.strip()

            # FILTRO 1: Ignora números de página soltos (ex: "12", "- 15 -", "iv")
            if re.match(r'^(?:\d{1,4}|[ivxlcdm]{1,6}|-\s*\d+\s*-)$', linha_limpa, re.IGNORECASE):
                continue

            # FILTRO 2: Ignora cabeçalhos repetitivos configurados
            if termo_filtro and termo_filtro in linha_limpa.lower() and len(linha_limpa) < 60:
                continue

            # FILTRO 3: Ignora linhas vazias ou ruídos muito curtos
            if len(linha_limpa) < 2:
                continue

            linhas_filtradas.append(linha_limpa)

        texto_pagina_limpo = " ".join(linhas_filtradas)

        # Agrupa em frases/parágrafos fluidos
        paragrafos = texto_pagina_limpo.split(". ")
        par_atual = ""
        for p in paragrafos:
            p_limpo = p.strip()
            if not p_limpo:
                continue
            par_atual += p_limpo + ". "
            if p_limpo.endswith((".", "!", "?", "”", '"', ":")):
                paragrafos_originais.append(par_atual.strip())
                par_atual = ""
        if par_atual.strip():
            paragrafos_originais.append(par_atual.strip())

    return paragrafos_originais

def extrair_texto_docx(conteudo_bytes: bytes) -> list[str]:
    """
    Lê o documento Word (.docx) e extrai parágrafos e células de tabelas.
    """
    paragrafos_originais = []
    doc = Document(io.BytesIO(conteudo_bytes))

    for p in doc.paragraphs:
        texto = p.text.strip()
        if len(texto) > 0:
            paragrafos_originais.append(re.sub(r'\s+', ' ', texto).strip())

    for tabela in doc.tables:
        for linha in tabela.rows:
            for celula in linha.cells:
                tc = re.sub(r'\s+', ' ', celula.text).strip()
                if len(tc) > 20 and tc not in paragrafos_originais:
                    paragrafos_originais.append(tc)

    return paragrafos_originais

def agrupar_em_lotes(paragrafos: list[str], tamanho_lote: int = 10000) -> list[str]:
    """
    Agrupa os parágrafos em partes de até tamanho_lote caracteres,
    preservando a quebra de parágrafo dupla ("\n\n").
    """
    partes = []
    bloco_atual = ""

    for par in paragrafos:
        if len(bloco_atual) + len(par) < tamanho_lote:
            bloco_atual += par + "\n\n"
        else:
            if bloco_atual.strip():
                partes.append(bloco_atual.strip())
            bloco_atual = par + "\n\n"

    if bloco_atual.strip():
        partes.append(bloco_atual.strip())

    return partes

# ---------------------------------------------------------
# Alinhamento de Palavras e Sincronização de Tempos
# ---------------------------------------------------------
def alinhar_pontuacao_e_paragrafos(texto_com_formatacao: str, tempos_brutos: list[dict]) -> list[dict]:
    """
    Alinha os tokens do texto original (com pontuação e marcadores de parágrafo)
    com os offsets retornados pelo Edge-TTS (WordBoundary).
    """
    if not tempos_brutos:
        return []

    tokens_originais = []
    paragrafos = texto_com_formatacao.split("\n\n")
    total_pars = len(paragrafos)

    for indice_par, paragrafo in enumerate(paragrafos):
        palavras_do_par = [p for p in paragrafo.split(" ") if p.strip()]
        total_pals = len(palavras_do_par)
        for idx_p, pal in enumerate(palavras_do_par):
            eh_fim_de_paragrafo = (idx_p == total_pals - 1) and (indice_par < total_pars - 1)
            texto_token = pal + ("\n\n" if eh_fim_de_paragrafo else "")
            limpa = re.sub(r'[^\w]', '', pal).lower()
            tokens_originais.append({"original": texto_token, "limpa": limpa})

    mapa_alinhado = []
    cursor_tempo = 0
    total_tempos = len(tempos_brutos)

    for token in tokens_originais:
        encontrou = False
        limite_busca = min(cursor_tempo + 5, total_tempos)
        for busca in range(cursor_tempo, limite_busca):
            palavra_tts_limpa = re.sub(r'[^\w]', '', tempos_brutos[busca]["palavra"]).lower()

            if token["limpa"] and (
                token["limpa"] == palavra_tts_limpa 
                or palavra_tts_limpa in token["limpa"] 
                or token["limpa"] in palavra_tts_limpa
            ):
                mapa_alinhado.append({
                    "palavra": token["original"],
                    "inicio": tempos_brutos[busca]["inicio"],
                    "fim": tempos_brutos[busca]["fim"]
                })
                cursor_tempo = busca + 1
                encontrou = True
                break

        if not encontrou:
            if mapa_alinhado:
                mapa_alinhado[-1]["palavra"] += " " + token["original"]
            elif total_tempos > 0:
                mapa_alinhado.append({
                    "palavra": token["original"],
                    "inicio": tempos_brutos[0]["inicio"],
                    "fim": tempos_brutos[0]["fim"]
                })

    return mapa_alinhado

# ---------------------------------------------------------
# Síntese Assíncrona via Edge-TTS
# ---------------------------------------------------------
async def gerar_parte_sincronizada(
    indice: int,
    total_partes: int,
    texto_parte: str,
    voz: str = "pt-BR-AntonioNeural",
    rate: str = "+0%",
    pitch: str = "-5Hz"
) -> tuple[bytes, list[dict], float]:
    """
    Sintetiza uma parte do texto com retry automático e captura eventos de WordBoundary.
    """
    for tentativa in range(1, 4):
        try:
            comunicador = edge_tts.Communicate(
                text=texto_parte,
                voice=voz,
                rate=rate,
                pitch=pitch,
                boundary="WordBoundary"
            )
            audio_bytes = bytearray()
            tempos_brutos = []

            async for chunk in comunicador.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    inicio = chunk["offset"] / 10_000_000
                    duracao = chunk["duration"] / 10_000_000
                    tempos_brutos.append({
                        "palavra": chunk["text"],
                        "inicio": inicio,
                        "fim": inicio + duracao
                    })

            if not audio_bytes:
                raise ValueError("Stream de áudio retornou vazio.")

            mp3_info = MP3(io.BytesIO(audio_bytes))
            duracao_real_bloco = mp3_info.info.length

            tempos_formatados = alinhar_pontuacao_e_paragrafos(texto_parte, tempos_brutos)

            logger.info(f"Parte {indice + 1}/{total_partes} concluída ({duracao_real_bloco:.1f}s | {len(tempos_formatados)} palavras)")
            return bytes(audio_bytes), tempos_formatados, duracao_real_bloco

        except Exception as e:
            logger.warning(f"Aviso: Tentativa {tentativa}/3 falhou para parte {indice + 1}: {e}")
            if tentativa < 3:
                await asyncio.sleep(5)

    logger.error(f"Falha definitiva ao sintetizar parte {indice + 1}")
    return b"", [], 0.0

# ---------------------------------------------------------
# Endpoints da API
# ---------------------------------------------------------
@app.get("/", tags=["Status"])
def root():
    return {
        "status": "online",
        "api": "Gerador de Audiolivro e Sincronizacao de Texto",
        "docs": "/docs",
        "health": "/health",
        "vozes": "/vozes"
    }

@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/vozes", tags=["Configuração"])
def listar_vozes():
    """Retorna uma lista de vozes recomendadas em Português."""
    return {
        "vozes_recomendadas": [
            {"id": "pt-BR-AntonioNeural", "genero": "Masculino", "idioma": "pt-BR", "padrao": True},
            {"id": "pt-BR-FranciscaNeural", "genero": "Feminino", "idioma": "pt-BR"},
            {"id": "pt-BR-ThalitaNeural", "genero": "Feminino", "idioma": "pt-BR"},
            {"id": "pt-PT-DuarteNeural", "genero": "Masculino", "idioma": "pt-PT"},
            {"id": "pt-PT-RaquelNeural", "genero": "Feminino", "idioma": "pt-PT"}
        ]
    }

@app.post("/processar-livro/", tags=["Processamento"])
async def processar_livro(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Arquivo .pdf ou .docx do livro/documento"),
    termo_cabecalho: Optional[str] = Form(None, description="Cabeçalho ou termo recorrente a ignorar (opcional)"),
    voz: str = Form("pt-BR-AntonioNeural", description="Voz do Edge-TTS"),
    rate: str = Form("+0%", description="Taxa de velocidade (ex: +0%, +10%, -5%)"),
    pitch: str = Form("-5Hz", description="Ajuste de tom (ex: -5Hz, +0Hz)"),
    tamanho_lote: int = Form(10000, description="Tamanho máximo de caracteres por lote"),
    retornar_mapa_inline: bool = Form(False, description="Se True, inclui a lista completa de palavras e tempos diretamente no JSON de resposta")
):
    """
    Recebe um arquivo PDF ou DOCX, extrai e limpa o texto,
    sintetiza a narração sincronizada via Edge-TTS e retorna
    as URLs para download do áudio .mp3 e mapa .json.
    """
    extensao = Path(file.filename or "").suffix.lower()
    if extensao not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não suportado. Envie um arquivo .pdf ou .docx."
        )

    # Limpeza de background periódica
    background_tasks.add_task(limpar_arquivos_antigos)

    # Gera identificador único e diretório para o job
    job_id = uuid.uuid4().hex
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Sanitiza o nome base do livro
    nome_original = Path(file.filename or "livro").stem
    nome_base_livro = re.sub(r'[^\w\s-]', '', nome_original).strip().replace(' ', '_')
    if not nome_base_livro:
        nome_base_livro = "audiolivro"

    logger.info(f"Iniciando processamento do livro '{nome_original}' (Job ID: {job_id})")

    # Lê o conteúdo do arquivo enviado
    conteudo_bytes = await file.read()
    if not conteudo_bytes:
        raise HTTPException(status_code=400, detail="O arquivo enviado está vazio.")

    # 1. Extração do texto
    try:
        if extensao == ".pdf":
            paragrafos_originais = extrair_texto_pdf(conteudo_bytes, termo_cabecalho)
        else:
            paragrafos_originais = extrair_texto_docx(conteudo_bytes)
    except Exception as e:
        logger.error(f"Erro ao extrair texto do arquivo: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar o arquivo: {str(e)}")

    if not paragrafos_originais:
        raise HTTPException(
            status_code=400,
            detail="Nenhum texto legível foi encontrado no arquivo fornecido."
        )

    # 2. Divisão em lotes
    partes = agrupar_em_lotes(paragrafos_originais, tamanho_lote=tamanho_lote)
    total_partes = len(partes)
    logger.info(f"Livro estruturado em {len(paragrafos_originais)} parágrafos e dividido em {total_partes} partes.")

    # 3. Processamento e síntese assíncrona
    arquivo_mp3 = job_dir / f"{nome_base_livro}_Audiolivro.mp3"
    arquivo_mapa = job_dir / f"{nome_base_livro}_MapaDoTempo.json"
    arquivo_info = job_dir / "info.json"

    mapa_completo = []
    tempo_acumulado = 0.0
    tamanho_grupo = 3

    try:
        with open(arquivo_mp3, "wb") as f_mp3:
            for i in range(0, total_partes, tamanho_grupo):
                lote = partes[i : i + tamanho_grupo]
                logger.info(f"Processando lote de partes {i + 1} até {min(i + tamanho_grupo, total_partes)}...")

                tarefas = [
                    gerar_parte_sincronizada(
                        indice=i + j,
                        total_partes=total_partes,
                        texto_parte=texto,
                        voz=voz,
                        rate=rate,
                        pitch=pitch
                    )
                    for j, texto in enumerate(lote)
                ]

                resultados = await asyncio.gather(*tarefas)

                for audio_bytes, tempos_parte, duracao_bloco in resultados:
                    if not audio_bytes:
                        continue

                    f_mp3.write(audio_bytes)

                    for item in tempos_parte:
                        mapa_completo.append({
                            "p": item["palavra"],
                            "i": round(item["inicio"] + tempo_acumulado, 3),
                            "f": round(item["fim"] + tempo_acumulado, 3)
                        })

                    tempo_acumulado += duracao_bloco

                # Pausa para respeitar limites de requisição do Edge-TTS
                if i + tamanho_grupo < total_partes:
                    await asyncio.sleep(5)

        # Salva o mapa sincronizado em JSON
        with open(arquivo_mapa, "w", encoding="utf-8") as f_json:
            json.dump(mapa_completo, f_json, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Erro durante a síntese de áudio: {e}")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Erro durante a síntese de áudio: {str(e)}")

    # Salva informações do job
    info_job = {
        "job_id": job_id,
        "nome_livro": nome_base_livro,
        "arquivo_original": file.filename,
        "duracao_segundos": round(tempo_acumulado, 2),
        "duracao_minutos": round(tempo_acumulado / 60, 2),
        "total_paragrafos": len(paragrafos_originais),
        "total_partes": total_partes,
        "total_palavras": len(mapa_completo),
        "criado_em": time.time(),
        "mp3_nome": arquivo_mp3.name,
        "json_nome": arquivo_mapa.name
    }

    with open(arquivo_info, "w", encoding="utf-8") as f_info:
        json.dump(info_job, f_info, ensure_ascii=False, indent=2)

    # Constrói URLs base dinamicamente com base no request atual
    base_url = str(request.base_url).rstrip("/")
    download_audio_url = f"{base_url}/download/{job_id}/audio"
    download_mapa_url = f"{base_url}/download/{job_id}/mapa"

    resposta = {
        "status": "sucesso",
        "job_id": job_id,
        "nome_livro": nome_base_livro,
        "duracao_segundos": round(tempo_acumulado, 2),
        "duracao_minutos": round(tempo_acumulado / 60, 2),
        "total_paragrafos": len(paragrafos_originais),
        "total_partes": total_partes,
        "total_palavras": len(mapa_completo),
        "download_audio_url": download_audio_url,
        "download_mapa_url": download_mapa_url
    }

    if retornar_mapa_inline:
        resposta["mapa"] = mapa_completo

    return resposta

@app.get("/download/{job_id}/audio", tags=["Download"])
def baixar_audio(job_id: str):
    """Retorna o arquivo de áudio MP3 compilado para reprodução ou download."""
    job_dir = STORAGE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")

    arquivos_mp3 = list(job_dir.glob("*_Audiolivro.mp3"))
    if not arquivos_mp3:
        raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado.")

    arquivo_mp3 = arquivos_mp3[0]
    return FileResponse(
        path=arquivo_mp3,
        media_type="audio/mpeg",
        filename=arquivo_mp3.name
    )

@app.get("/download/{job_id}/mapa", tags=["Download"])
def baixar_mapa(job_id: str):
    """Retorna o arquivo JSON com o mapa de sincronização de tempos e palavras."""
    job_dir = STORAGE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")

    arquivos_mapa = list(job_dir.glob("*_MapaDoTempo.json"))
    if not arquivos_mapa:
        raise HTTPException(status_code=404, detail="Arquivo de mapa JSON não encontrado.")

    arquivo_mapa = arquivos_mapa[0]
    return FileResponse(
        path=arquivo_mapa,
        media_type="application/json",
        filename=arquivo_mapa.name
    )

@app.get("/status/{job_id}", tags=["Status"])
def status_job(job_id: str):
    """Consulta os metadados de um processamento específico."""
    job_dir = STORAGE_DIR / job_id
    arquivo_info = job_dir / "info.json"

    if not arquivo_info.exists():
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")

    with open(arquivo_info, "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    import uvicorn
    # Permite rodar diretamente via 'python app.py' para testes locais
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
