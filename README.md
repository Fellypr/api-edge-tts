---
title: Gerador de Audiolivro e Mapa de Tempo
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🎧 API de Geração de Audiolivro e Sincronização de Texto

Esta API foi construída com **FastAPI** e **Edge-TTS**, configurada para deploy gratuito no **Hugging Face Spaces** utilizando o **Docker SDK**.

A API converte arquivos de texto (`.pdf` ou `.docx`) em audiolivros `.mp3` de alta qualidade com vozes neurais da Microsoft, além de gerar um mapa temporal preciso (`.json`) com início e término de cada palavra para sincronização visual (karaokê/leitura acompanhada) no seu front-end.

---

## 🚀 Como Integrar com seu Site (Frontend)

### 1. Enviar arquivo para processamento (`POST /processar-livro/`)

```javascript
const formData = new FormData();
formData.append("file", fileInput.files[0]); // Arquivo .pdf ou .docx
formData.append("voz", "pt-BR-AntonioNeural"); // Opcional (padrão: pt-BR-AntonioNeural)
formData.append("rate", "+0%");               // Opcional (velocidade)
formData.append("pitch", "-5Hz");             // Opcional (tom da voz)
formData.append("retornar_mapa_inline", "false"); // Opcional

const response = await fetch("https://SEU-SPACE.hf.space/processar-livro/", {
  method: "POST",
  body: formData
});

const data = await response.json();
console.log("Resultado:", data);
/*
Retorno:
{
  "status": "sucesso",
  "job_id": "c1f7b8...",
  "nome_livro": "meu_livro",
  "duracao_segundos": 142.3,
  "duracao_minutos": 2.37,
  "total_paragrafos": 24,
  "total_partes": 2,
  "total_palavras": 1820,
  "download_audio_url": "https://SEU-SPACE.hf.space/download/c1f7b8.../audio",
  "download_mapa_url": "https://SEU-SPACE.hf.space/download/c1f7b8.../mapa"
}
*/
```

### 2. Consumir o Áudio no HTML5 Player

```html
<audio id="audioPlayer" controls src="https://SEU-SPACE.hf.space/download/JOB_ID/audio"></audio>
```

### 3. Sincronizar o Texto com o Tempo do Áudio

Baixe o JSON através da URL fornecida em `download_mapa_url`:
```javascript
const mapa = await fetch(data.download_mapa_url).then(r => r.json());

// Durante a reprodução do áudio:
audioPlayer.addEventListener("timeupdate", () => {
  const tempoAtual = audioPlayer.currentTime;
  const palavraAtiva = mapa.find(item => tempoAtual >= item.i && tempoAtual <= item.f);
  if (palavraAtiva) {
    // Destacar palavra na interface
    console.log("Palavra atual:", palavraAtiva.p);
  }
});
```

---

## 📌 Documentação Interativa (Swagger)

Acesse `/docs` na URL do seu Space para testar os endpoints interativamente pela interface web.
