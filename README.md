---
title: Gerador de Audiolivro e Mapa de Tempo
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🎧 API de Geração de Audiolivro e Sincronização de Texto (v2.0)

Esta API foi construída com **FastAPI** e **Edge-TTS**, configurada para deploy gratuito no **Hugging Face Spaces** utilizando o **Docker SDK**.

A API converte arquivos de texto (`.pdf` ou `.docx`) em audiolivros `.mp3` de alta qualidade com vozes neurais da Microsoft, além de gerar um mapa temporal preciso (`.json`) com início e término de cada palavra para sincronização visual (karaokê/leitura acompanhada) no seu front-end.

A versão **2.0** conta com **túnel Server-Sent Events (SSE)** em tempo real, permitindo ao frontend receber logs do servidor e barra de progresso instantânea enquanto o áudio é processado.

---

## 🚀 Como Integrar com seu Site (Frontend)

### 1. Enviar arquivo para processamento (`POST /processar-livro/`)

```javascript
const formData = new FormData();
formData.append("file", fileInput.files[0]); // Arquivo .pdf ou .docx
formData.append("voz", "pt-BR-AntonioNeural"); // Opcional (padrão: pt-BR-AntonioNeural)
formData.append("rate", "+0%");               // Opcional (velocidade)
formData.append("pitch", "-5Hz");             // Opcional (tom da voz)

// Retorno imediato do job
const response = await fetch("https://SEU-SPACE.hf.space/processar-livro/", {
  method: "POST",
  body: formData
});

const data = await response.json();
console.log("Job iniciado:", data);
/*
Retorno imediato:
{
  "status": "iniciado",
  "job_id": "c1f7b8...",
  "stream_url": "https://SEU-SPACE.hf.space/jobs/c1f7b8.../stream",
  "status_url": "https://SEU-SPACE.hf.space/status/c1f7b8...",
  "download_audio_url": "https://SEU-SPACE.hf.space/download/c1f7b8.../audio",
  "download_mapa_url": "https://SEU-SPACE.hf.space/download/c1f7b8.../mapa"
}
*/
```

### 2. Abrir o Túnel de Logs em Tempo Real (`EventSource` / SSE)

Conecte no `stream_url` retornado pelo passo anterior para transmitir logs e porcentagem ao vivo para a interface:

```javascript
const eventSource = new EventSource(data.stream_url);

eventSource.onmessage = (event) => {
  const evento = JSON.parse(event.data);

  if (evento.tipo === "log") {
    console.log(`[${evento.tempo}] [${evento.nivel}] ${evento.mensagem}`);
  }

  if (evento.tipo === "progresso") {
    console.log(`Progresso: ${evento.porcentagem}% - ${evento.mensagem}`);
  }

  if (evento.tipo === "concluido") {
    console.log("Processamento concluído!", evento);
    eventSource.close();
    // Iniciar reprodução com evento.download_audio_url e evento.download_mapa_url
  }

  if (evento.tipo === "erro") {
    console.error("Erro no processamento:", evento.mensagem);
    eventSource.close();
  }
};
```

### 3. Consumir o Áudio no HTML5 Player

```html
<audio id="audioPlayer" controls src="https://SEU-SPACE.hf.space/download/JOB_ID/audio"></audio>
```

### 4. Sincronizar o Texto com o Tempo do Áudio

Baixe o JSON através da URL fornecida em `download_mapa_url`:
```javascript
const mapa = await fetch(download_mapa_url).then(r => r.json());

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
