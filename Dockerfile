# Imagem base otimizada com Python 3.11 Slim
FROM python:3.11-slim

# Evita geração de arquivos .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# O Hugging Face Spaces executa containers com o usuário UID 1000
RUN useradd -m -u 1000 user

# Define variáveis de ambiente do usuário
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Instala as dependências Python no diretório do usuário
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Copia todo o código-fonte com as permissões corretas
COPY --chown=user:user . .

# Cria pasta de armazenamento e garante permissão de escrita
RUN mkdir -p $HOME/app/storage && chown -R user:user $HOME/app/storage

# Altera para o usuário UID 1000
USER user

# Hugging Face Spaces espera a aplicação escutando na porta 7860
EXPOSE 7860

# Comando para iniciar o servidor FastAPI via Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
